#pragma once

#include <cstdlib>
#include <mutex>
#include <stdexcept>
#include <string>

#include "database/databasemanager.hpp"

class TestDatabase final {
public:
	static void init() {
		static std::once_flag initialized;
		std::call_once(initialized, [] {
			const char* schema = std::getenv("TEST_DB_SCHEMA");
			if (!schema || !*schema) {
				schema = TESTS_SCHEMA_DEFAULT;
			}
			if (!g_database().connect(":memory:") || !DatabaseManager::initializeDatabase(schema)) {
				throw std::runtime_error("Failed to initialize the in-memory integration test database");
			}
		});
	}
};
