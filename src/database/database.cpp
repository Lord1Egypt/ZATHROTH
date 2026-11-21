/**
 * Canary - A free and open-source MMORPG server emulator
 * Copyright (©) 2019–present OpenTibiaBR <opentibiabr@outlook.com>
 * Repository: https://github.com/opentibiabr/canary
 * License: https://github.com/opentibiabr/canary/blob/main/LICENSE
 * Contributors: https://github.com/opentibiabr/canary/graphs/contributors
 * Website: https://docs.opentibiabr.com/
 */

#include "database/database.hpp"

#include "config/configmanager.hpp"
#include "lib/di/container.hpp"
#include "lib/metrics/metrics.hpp"
#include <sqlite3.h>

#ifndef USE_PRECOMPILED_HEADERS
	#include <algorithm>
	#include <chrono>
	#include <filesystem>
	#include <fstream>
	#include <fmt/chrono.h>
	#include <fmt/format.h>
	#include <zlib.h>
#endif

namespace {

	using Statement = std::unique_ptr<sqlite3_stmt, decltype(&sqlite3_finalize)>;

	bool compressBackup(const std::string &source, const std::string &destination) {
		std::ifstream input(source, std::ios::binary);
		if (!input) {
			return false;
		}
		gzFile output = gzopen(destination.c_str(), "wb9");
		if (!output) {
			return false;
		}
		char buffer[8192];
		bool written = true;
		while (input.read(buffer, sizeof(buffer)) || input.gcount() > 0) {
			auto size = static_cast<unsigned int>(input.gcount());
			if (gzwrite(output, buffer, size) != size) {
				written = false;
				break;
			}
		}
		return gzclose(output) == Z_OK && written && !input.bad();
	}

}

Database::~Database() {
	if (handle) {
		sqlite3_close(handle);
	}
}

Database &Database::getInstance() {
	return inject<Database>();
}

const char* Database::getClientVersion() {
	return sqlite3_libversion();
}

bool Database::connect() {
	return connect(g_configManager().getString(SQLITE_DB));
}

bool Database::connect(const std::string &path) {
	std::scoped_lock lock(databaseLock);
	if (handle) {
		return path == databasePath;
	}
	if (path.empty()) {
		g_logger().error("SQLite database path is empty");
		return false;
	}

	sqlite3* opened = nullptr;
	const int status = sqlite3_open_v2(path.c_str(), &opened, SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE, nullptr);
	std::unique_ptr<sqlite3, decltype(&sqlite3_close)> connection(opened, sqlite3_close);
	if (status != SQLITE_OK) {
		g_logger().error("Could not open SQLite database '{}': {}", path, sqlite3_errstr(status));
		return false;
	}

	sqlite3_busy_timeout(opened, 5000);
	sqlite3_db_config(opened, SQLITE_DBCONFIG_DQS_DML, 0, nullptr);
	sqlite3_db_config(opened, SQLITE_DBCONFIG_DQS_DDL, 0, nullptr);
	if (sqlite3_exec(opened, "PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL; PRAGMA synchronous = NORMAL", nullptr, nullptr, nullptr) != SQLITE_OK) {
		g_logger().error("Could not configure SQLite database '{}': {}", path, sqlite3_errmsg(opened));
		return false;
	}
	databasePath = path;
	handle = connection.release();
	lastInsertId = 0;
	return true;
}

void Database::createDatabaseBackup(bool compress) {
	if (!g_configManager().getBoolean(SQLITE_DB_BACKUP)) {
		return;
	}

	try {
		const auto now = std::chrono::system_clock::now();
		const auto backupDirectory = std::filesystem::path(g_configManager().getString(SQLITE_DB)).parent_path() / "database_backup" / fmt::format("{:%Y-%m-%d}", now);
		std::filesystem::create_directories(backupDirectory);
		const auto suffix = std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()).count();
		const auto filename = (backupDirectory / fmt::format("backup_{}.sqlite3", suffix)).string();

		if (!executeQuery("VACUUM INTO " + escapeString(filename))) {
			g_logger().error("Failed to create SQLite database backup");
			return;
		}

		auto savedFile = filename;
		if (compress) {
			const auto compressedFile = filename + ".gz";
			if (compressBackup(filename, compressedFile)) {
				std::filesystem::remove(filename);
				savedFile = compressedFile;
			} else {
				std::filesystem::remove(compressedFile);
				g_logger().warn("Could not compress database backup '{}'", filename);
			}
		}
		g_logger().info("Database backup saved to {}", savedFile);

		const auto cutoff = std::filesystem::file_time_type::clock::now() - std::chrono::hours(7 * 24);
		for (const auto &entry : std::filesystem::recursive_directory_iterator(backupDirectory.parent_path())) {
			const auto path = entry.path().filename().string();
			if (entry.is_regular_file() && path.starts_with("backup_") && (path.ends_with(".sqlite3") || path.ends_with(".sqlite3.gz")) && entry.last_write_time() < cutoff) {
				std::filesystem::remove(entry.path());
			}
		}
	} catch (const std::filesystem::filesystem_error &error) {
		g_logger().error("Could not manage SQLite backups: {}", error.what());
	}
}

sqlite3_stmt* Database::prepareQuery(std::string_view query) {
	if (!handle) {
		g_logger().error("Database not initialized");
		return nullptr;
	}
	if (query.empty() || query.size() > MAX_QUERY_SIZE || query.find('\0') != std::string_view::npos) {
		g_logger().error("Invalid SQLite query length or contents");
		return nullptr;
	}

	sqlite3_stmt* raw = nullptr;
	const char* tail = nullptr;
	const int status = sqlite3_prepare_v2(handle, query.data(), static_cast<int>(query.size()), &raw, &tail);
	Statement statement(raw, sqlite3_finalize);
	if (status != SQLITE_OK) {
		g_logger().error("Could not prepare SQLite query: {}", sqlite3_errmsg(handle));
		return nullptr;
	}
	if (!statement) {
		return nullptr;
	}

	const std::string_view remainder(tail, query.data() + query.size() - tail);
	if (remainder.find_first_not_of(" \t\r\n") != std::string_view::npos) {
		g_logger().error("Multiple SQLite statements are not supported");
		return nullptr;
	}
	return statement.release();
}

bool Database::executeScript(const std::string &script) {
	std::scoped_lock lock(databaseLock);
	if (!handle || sqlite3_exec(handle, script.c_str(), nullptr, nullptr, nullptr) != SQLITE_OK) {
		g_logger().error("Could not initialize SQLite schema: {}", handle ? sqlite3_errmsg(handle) : "database not initialized");
		return false;
	}
	return true;
}

bool Database::executeQuery(std::string_view query) {
	metrics::lock_latency measureLock("database");
	std::scoped_lock lock(databaseLock);
	measureLock.stop();

	metrics::query_latency measure(query.substr(0, 50));
	Statement statement(prepareQuery(query), sqlite3_finalize);
	if (!statement) {
		return false;
	}
	const auto firstToken = query.find_first_not_of(" \t\r\n");
	const auto keyword = query.substr(firstToken, 6);
	const bool isInsert = keyword.size() == 6 && (sqlite3_strnicmp(keyword.data(), "INSERT", 6) == 0);
	if (isInsert) {
		sqlite3_set_last_insert_rowid(handle, 0);
		lastInsertId = 0;
	}

	int status;
	do {
		status = sqlite3_step(statement.get());
	} while (status == SQLITE_ROW);
	if (status != SQLITE_DONE) {
		g_logger().error("SQLite query failed: {}", sqlite3_errmsg(handle));
		return false;
	}
	if (isInsert) {
		lastInsertId = static_cast<uint64_t>(sqlite3_last_insert_rowid(handle));
	}
	return true;
}

DBResult_ptr Database::storeQuery(std::string_view query) {
	metrics::lock_latency measureLock("database");
	std::scoped_lock lock(databaseLock);
	measureLock.stop();

	metrics::query_latency measure(query.substr(0, 50));
	Statement statement(prepareQuery(query), sqlite3_finalize);
	if (!statement) {
		return nullptr;
	}

	auto result = DBResult_ptr(new DBResult());
	const int columns = sqlite3_column_count(statement.get());
	for (int column = 0; column < columns; ++column) {
		result->listNames[sqlite3_column_name(statement.get(), column)] = column;
	}

	int status;
	while ((status = sqlite3_step(statement.get())) == SQLITE_ROW) {
		auto &row = result->rows.emplace_back();
		row.reserve(columns);
		for (int column = 0; column < columns; ++column) {
			if (sqlite3_column_type(statement.get(), column) == SQLITE_NULL) {
				row.emplace_back(std::nullopt);
				continue;
			}

			const auto* bytes = static_cast<const char*>(sqlite3_column_blob(statement.get(), column));
			const auto size = sqlite3_column_bytes(statement.get(), column);
			row.emplace_back(std::in_place, bytes ? bytes : "", size);
		}
	}

	if (status != SQLITE_DONE) {
		g_logger().error("SQLite query failed: {}", sqlite3_errmsg(handle));
		return nullptr;
	}
	return result->hasNext() ? result : nullptr;
}

std::string Database::escapeString(const std::string &s) const {
	if (s.find('\0') != std::string::npos) {
		return "CAST(" + escapeBlob(s.data(), static_cast<uint32_t>(s.size())) + " AS TEXT)";
	}
	std::string escaped;
	escaped.reserve(s.size() + 2);
	escaped.push_back('\'');
	for (char c : s) {
		escaped.push_back(c);
		if (c == '\'') {
			escaped.push_back(c);
		}
	}
	escaped.push_back('\'');
	return escaped;
}

std::string Database::escapeBlob(const char* data, uint32_t length) const {
	constexpr std::string_view hex = "0123456789abcdef";
	std::string escaped = "X'";
	escaped.reserve(static_cast<size_t>(length) * 2 + 3);
	for (uint32_t i = 0; i < length; ++i) {
		auto value = static_cast<unsigned char>(data[i]);
		escaped.push_back(hex[value >> 4]);
		escaped.push_back(hex[value & 15]);
	}
	escaped.push_back('\'');
	return escaped;
}

std::string DBResult::getString(const std::string &s) const {
	unsigned long size;
	const char* data = getStream(s, size);
	return data ? std::string(data, size) : std::string();
}

const char* DBResult::getStream(const std::string &s, unsigned long &size) const {
	size = 0;
	auto it = listNames.find(s);
	if (it == listNames.end()) {
		g_logger().error("Column '{}' does not exist in the result set", s);
		return nullptr;
	}
	if (!hasNext()) {
		return nullptr;
	}
	const auto &value = rows[row][it->second];
	if (!value) {
		return nullptr;
	}

	size = value->size();
	return value->c_str();
}

uint8_t DBResult::getU8FromString(const std::string &string, const std::string &function) {
	auto result = static_cast<uint8_t>(std::atoi(string.c_str()));
	if (result > std::numeric_limits<uint8_t>::max()) {
		g_logger().error("[{}] Failed to get number value {} for tier table result, on function call: {}", __FUNCTION__, result, function);
		return 0;
	}

	return result;
}

int8_t DBResult::getInt8FromString(const std::string &string, const std::string &function) {
	auto result = static_cast<int8_t>(std::atoi(string.c_str()));
	if (result > std::numeric_limits<int8_t>::max()) {
		g_logger().error("[{}] Failed to get number value {} for tier table result, on function call: {}", __FUNCTION__, result, function);
		return 0;
	}

	return result;
}

size_t DBResult::countResults() const {
	return rows.size();
}

bool DBResult::hasNext() const {
	return row < rows.size();
}

bool DBResult::next() {
	if (hasNext()) {
		++row;
	}
	return hasNext();
}

DBInsert::DBInsert(std::string insertQuery) :
	query(std::move(insertQuery)) {
	if (!query.empty() && query.back() != ' ') {
		query.push_back(' ');
	}
}

bool DBInsert::addRow(std::string_view row) {
	const size_t addedLength = row.size() + 2;
	const size_t statementLength = query.size() + upsertClause.size() + addedLength;
	if (statementLength > Database::MAX_QUERY_SIZE) {
		return false;
	}
	if (!values.empty() && statementLength + values.size() + 1 > Database::MAX_QUERY_SIZE && !execute()) {
		return false;
	}

	if (!values.empty()) {
		values.push_back(',');
	}
	values.push_back('(');
	values.append(row);
	values.push_back(')');
	return true;
}

bool DBInsert::addRow(std::ostringstream &row) {
	const bool added = addRow(row.str());
	row.str(std::string());
	return added;
}

void DBInsert::upsert(const std::vector<std::string> &columns) {
	upsertClause.clear();
	if (columns.empty()) {
		return;
	}
	upsertClause = " ON CONFLICT DO UPDATE SET ";
	for (size_t i = 0; i < columns.size(); ++i) {
		if (i > 0) {
			upsertClause += ", ";
		}
		upsertClause += fmt::format("`{0}` = excluded.`{0}`", columns[i]);
	}
}

bool DBInsert::execute() {
	if (values.empty()) {
		return true;
	}
	if (!g_database().executeQuery(query + values + upsertClause)) {
		return false;
	}
	values.clear();
	return true;
}

DBTransaction::DBTransaction(Database &database) :
	database(database), lock(database.databaseLock) {
	nested = database.handle && !sqlite3_get_autocommit(database.handle);
	active = database.executeQuery(nested ? "SAVEPOINT server_transaction" : "BEGIN IMMEDIATE");
}

DBTransaction::~DBTransaction() {
	if (active && !sqlite3_get_autocommit(database.handle)) {
		const auto* rollback = nested ? "ROLLBACK TO server_transaction; RELEASE server_transaction" : "ROLLBACK";
		sqlite3_exec(database.handle, rollback, nullptr, nullptr, nullptr);
	}
}

bool DBTransaction::commit() {
	if (!database.executeQuery(nested ? "RELEASE server_transaction" : "COMMIT")) {
		return false;
	}
	active = false;
	return true;
}
