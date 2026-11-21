/**
 * Canary - A free and open-source MMORPG server emulator
 * Copyright (©) 2019–present OpenTibiaBR <opentibiabr@outlook.com>
 * Repository: https://github.com/opentibiabr/canary
 * License: https://github.com/opentibiabr/canary/blob/main/LICENSE
 * Contributors: https://github.com/opentibiabr/canary/graphs/contributors
 * Website: https://docs.opentibiabr.com/
 */

#include "database/databasemanager.hpp"

#include "config/configmanager.hpp"
#include "lua/functions/core/libs/core_libs_functions.hpp"
#include "lua/scripts/luascript.hpp"
#include "utils/benchmark.hpp"

#ifndef USE_PRECOMPILED_HEADERS
	#include <algorithm>
	#include <filesystem>
	#include <fstream>
	#include <regex>
	#include <fmt/format.h>
#endif

namespace InternalDBManager {
	int32_t extractVersionFromFilename(const std::string &filename) {
		std::regex versionRegex(R"((\d+)\.lua)");
		std::smatch match;

		if (std::regex_search(filename, match, versionRegex) && match.size() > 1) {
			return std::stoi(match.str(1));
		}

		return -1;
	}
}

bool DatabaseManager::optimizeTables() {
	return g_database().executeQuery("PRAGMA optimize");
}

bool DatabaseManager::tableExists(const std::string &tableName) {
	auto &db = g_database();
	return db.storeQuery("SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = " + db.escapeString(tableName) + " COLLATE NOCASE LIMIT 1") != nullptr;
}

bool DatabaseManager::initializeDatabase(const std::string &schemaPath) {
	// Historical migrations through version 59 target MySQL. A new SQLite
	// database starts at this baseline and only applies later migrations.
	constexpr int32_t sqliteBaselineVersion = 59;
	auto &db = g_database();
	return DBTransaction::executeWithinTransactionRollbackOnFailure([&]() {
		if (!tableExists("server_config")) {
			if (db.storeQuery("SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name NOT GLOB 'sqlite_*' LIMIT 1")) {
				g_logger().error("SQLite database has tables but no server_config; database schema is unrecognized");
				return false;
			}
			std::ifstream schema(schemaPath, std::ios::binary);
			if (!schema) {
				g_logger().error("Could not read SQLite schema from '{}'", schemaPath);
				return false;
			}
			std::ostringstream contents;
			contents << schema.rdbuf();
			if (schema.bad() || !db.executeScript(contents.str())) {
				return false;
			}
		}

		const auto version = getDatabaseVersion();
		if (version < sqliteBaselineVersion || !tableExists("accounts") || !tableExists("players")) {
			g_logger().error("Unsupported SQLite database schema version {}", version);
			return false;
		}
		return true;
	});
}

int32_t DatabaseManager::getDatabaseVersion() {
	int32_t version = -1;
	getDatabaseConfig("db_version", version);
	return version;
}

void DatabaseManager::updateDatabase() {
	Benchmark bm;
	lua_State* L = luaL_newstate();
	if (!L) {
		return;
	}

	luaL_openlibs(L);
	CoreLibsFunctions::init(L);

	int32_t currentVersion = getDatabaseVersion();
	std::string migrationDirectory = g_configManager().getString(DATA_DIRECTORY) + "/migrations/";

	std::vector<std::pair<int32_t, std::string>> migrations;

	if (!std::filesystem::is_directory(migrationDirectory)) {
		lua_close(L);
		return;
	}

	for (const auto &entry : std::filesystem::directory_iterator(migrationDirectory)) {
		if (entry.is_regular_file()) {
			std::string filename = entry.path().filename().string();
			int32_t fileVersion = InternalDBManager::extractVersionFromFilename(filename);
			migrations.emplace_back(fileVersion, entry.path().string());
		}
	}

	std::sort(migrations.begin(), migrations.end());

	for (const auto &[fileVersion, scriptPath] : migrations) {
		if (fileVersion > currentVersion) {
			if (!LuaScriptInterface::reserveScriptEnv()) {
				break;
			}

			if (luaL_dofile(L, scriptPath.c_str()) != 0) {
				g_logger().error("DatabaseManager::updateDatabase - Version: {}] {}", fileVersion, lua_tostring(L, -1));
				LuaScriptInterface::resetScriptEnv();
				continue;
			}

			lua_getglobal(L, "onUpdateDatabase");
			if (lua_pcall(L, 0, 1, 0) != 0) {
				LuaScriptInterface::resetScriptEnv();
				g_logger().warn("[DatabaseManager::updateDatabase - Version: {}] {}", fileVersion, lua_tostring(L, -1));
				continue;
			}

			currentVersion = fileVersion;
			g_logger().info("Database has been updated to version {}", currentVersion);
			registerDatabaseConfig("db_version", currentVersion);

			LuaScriptInterface::resetScriptEnv();
		}
	}

	double duration = bm.duration();
	if (duration < 1000.0) {
		g_logger().debug("Database update completed in {:.2f} ms", duration);
	} else {
		g_logger().debug("Database update completed in {:.2f} seconds", duration / 1000.0);
	}
	lua_close(L);
}

bool DatabaseManager::getDatabaseConfig(const std::string &config, int32_t &value) {
	Database &db = Database::getInstance();
	std::ostringstream query;
	query << "SELECT `value` FROM `server_config` WHERE `config` = " << db.escapeString(config);

	DBResult_ptr result = db.storeQuery(query.str());
	if (!result) {
		return false;
	}

	value = result->getNumber<int32_t>("value");
	return true;
}

void DatabaseManager::registerDatabaseConfig(const std::string &config, int32_t value) {
	auto &db = g_database();
	db.executeQuery(fmt::format(
		"INSERT INTO `server_config` (`config`, `value`) VALUES ({}, {}) "
		"ON CONFLICT (`config`) DO UPDATE SET `value` = excluded.`value`",
		db.escapeString(config), value
	));
}
