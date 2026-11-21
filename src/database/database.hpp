/**
 * Canary - A free and open-source MMORPG server emulator
 * Copyright (©) 2019–present OpenTibiaBR <opentibiabr@outlook.com>
 * Repository: https://github.com/opentibiabr/canary
 * License: https://github.com/opentibiabr/canary/blob/main/LICENSE
 * Contributors: https://github.com/opentibiabr/canary/graphs/contributors
 * Website: https://docs.opentibiabr.com/
 */

#pragma once

#include "declarations.hpp"

#include "lib/logging/logger.hpp"

#ifndef USE_PRECOMPILED_HEADERS
	#include <map>
	#include <memory>
	#include <mutex>
	#include <optional>
	#include <sstream>
	#include <string>
	#include <string_view>
	#include <type_traits>
	#include <utility>
	#include <vector>
#endif

struct sqlite3;
struct sqlite3_stmt;

class DBResult;
using DBResult_ptr = std::shared_ptr<DBResult>;

class Database {
public:
	static constexpr size_t MAX_QUERY_SIZE = 8 * 1024 * 1024;

	Database() = default;
	~Database();

	Database(const Database &) = delete;
	Database &operator=(const Database &) = delete;

	static Database &getInstance();

	bool connect();
	bool connect(const std::string &path);
	void createDatabaseBackup(bool compress);

	bool executeQuery(std::string_view query);
	DBResult_ptr storeQuery(std::string_view query);

	std::string escapeString(const std::string &s) const;
	std::string escapeBlob(const char* s, uint32_t length) const;

	uint64_t getLastInsertId() const {
		return lastInsertId;
	}

	static const char* getClientVersion();

private:
	sqlite3_stmt* prepareQuery(std::string_view query);
	bool executeScript(const std::string &script);

	std::string databasePath;
	sqlite3* handle = nullptr;
	std::recursive_mutex databaseLock;
	inline static thread_local uint64_t lastInsertId = 0;

	friend class DatabaseManager;
	friend class DBTransaction;
};

constexpr auto g_database = Database::getInstance;

class DBResult {
public:
	// Non copyable
	DBResult(const DBResult &) = delete;
	DBResult &operator=(const DBResult &) = delete;

	template <typename T>
	T getNumber(const std::string &s) const {
		unsigned long size;
		const char* value = getStream(s, size);
		if (!value) {
			return T();
		}

		T data {};
		try {
			// Check if the type T is a enum
			if constexpr (std::is_enum_v<T>) {
				using underlying_type = std::underlying_type_t<T>;
				underlying_type number = 0;
				if constexpr (std::is_signed_v<underlying_type>) {
					number = static_cast<underlying_type>(std::stoll(value));
				} else {
					number = static_cast<underlying_type>(std::stoull(value));
				}
				return static_cast<T>(number);
			}
			// Check if the type T is signed or unsigned
			if constexpr (std::is_signed_v<T>) {
				// Check if the type T is int8_t or int16_t
				if constexpr (std::is_same_v<T, int8_t> || std::is_same_v<T, int16_t>) {
					// Use std::stoi to convert string to int8_t
					data = static_cast<T>(std::stoi(value));
				}
				// Check if the type T is int32_t
				else if constexpr (std::is_same_v<T, int32_t>) {
					// Use std::stol to convert string to int32_t
					data = static_cast<T>(std::stol(value));
				}
				// Check if the type T is int64_t
				else if constexpr (std::is_same_v<T, int64_t>) {
					// Use std::stoll to convert string to int64_t
					data = static_cast<T>(std::stoll(value));
				}
				// Check if the type T is time_t
				else if constexpr (std::is_same_v<T, time_t>) {
					// Use std::stoll to convert string to time_t (usually long long)
					data = static_cast<T>(std::stoll(value));
				} else {
					// Throws exception indicating that type T is invalid
					g_logger().error("Invalid signed type T");
				}
			} else if (std::is_same<T, bool>::value) {
				data = static_cast<T>(std::stoi(value));
			} else {
				// Check if the type T is uint8_t or uint16_t or uint32_t
				if constexpr (std::is_same_v<T, uint8_t> || std::is_same_v<T, uint16_t> || std::is_same_v<T, uint32_t>) {
					// Use std::stoul to convert string to uint8_t
					data = static_cast<T>(std::stoul(value));
				}
				// Check if the type T is uint64_t
				else if constexpr (std::is_same_v<T, uint64_t>) {
					// Use std::stoull to convert string to uint64_t
					data = static_cast<T>(std::stoull(value));
				} else {
					// Send log indicating that type T is invalid
					g_logger().error("Column '{}' has an invalid unsigned T is invalid", s);
				}
			}
		} catch (std::invalid_argument &e) {
			// Value of string is invalid
			g_logger().error("Column '{}' has an invalid value set, error code: {}", s, e.what());
			data = T();
		} catch (std::out_of_range &e) {
			// Value of string is too large to fit the range allowed by type T
			g_logger().error("Column '{}' has a value out of range, error code: {}", s, e.what());
			data = T();
		}

		return data;
	}

	std::string getString(const std::string &s) const;
	const char* getStream(const std::string &s, unsigned long &size) const;
	static uint8_t getU8FromString(const std::string &string, const std::string &function);
	static int8_t getInt8FromString(const std::string &string, const std::string &function);

	size_t countResults() const;
	bool hasNext() const;
	bool next();

private:
	DBResult() = default;

	using Cell = std::optional<std::string>;
	std::vector<std::vector<Cell>> rows;
	std::map<std::string, size_t> listNames;
	size_t row = 0;

	friend class Database;
};

/**
 * INSERT statement.
 */
class DBInsert {
public:
	explicit DBInsert(std::string query);
	void upsert(const std::vector<std::string> &columns);
	bool addRow(std::string_view row);
	bool addRow(std::ostringstream &row);
	bool execute();

private:
	std::string query;
	std::string values;
	std::string upsertClause;
};

class DBTransaction {
public:
	~DBTransaction();

	DBTransaction(const DBTransaction &) = delete;
	DBTransaction &operator=(const DBTransaction &) = delete;

	template <typename Func>
	static bool executeWithinTransaction(const Func &callback)
		requires std::invocable<Func>
	{
		return execute(callback, false);
	}

	template <typename Func>
	static bool executeWithinTransactionRollbackOnFailure(const Func &callback)
		requires std::invocable<Func>
	{
		return execute(callback, true);
	}

private:
	explicit DBTransaction(Database &database);

	template <typename Func>
	static bool execute(const Func &callback, bool rollbackOnFailure) {
		try {
			DBTransaction transaction(g_database());
			if (!transaction.active) {
				return false;
			}
			const bool succeeded = callback();
			if (!succeeded && rollbackOnFailure) {
				return false;
			}
			return transaction.commit() && succeeded;
		} catch (const std::exception &error) {
			g_logger().error("Error during database transaction: {}", error.what());
			return false;
		}
	}

	bool commit();

	Database &database;
	std::unique_lock<std::recursive_mutex> lock;
	bool active = false;
	bool nested = false;
};

class DatabaseException : public std::exception {
public:
	explicit DatabaseException(std::string message) :
		message(std::move(message)) { }

	const char* what() const noexcept override {
		return message.c_str();
	}

private:
	std::string message;
};
