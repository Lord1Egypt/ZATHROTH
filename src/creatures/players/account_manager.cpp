/**
 * ZATHROTH - In-game Account Manager
 * License: GPL-2.0 (see LICENSE)
 */

#include "creatures/players/account_manager.hpp"

#include "creatures/players/player.hpp"
#include "creatures/players/vocations/vocation.hpp"
#include "database/database.hpp"
#include "utils/tools.hpp"

#include <argon2.h>

namespace account_manager_rules {
	// Keep these rules in step with account_manager/storage.py so the browser
	// and in-game managers accept the same names and passwords.
	constexpr uint32_t MAX_CHARACTERS = 20;
	constexpr std::array<uint16_t, 5> START_VOCATIONS = { 1, 2, 3, 4, 9 };
	constexpr time_t DELETION_DELAY = 7 * 24 * 60 * 60;
	const std::regex ACCOUNT_NAME("[a-zA-Z0-9][a-zA-Z0-9_-]{2,31}");
	const std::regex CHARACTER_NAME("[a-zA-Z]+(?:[ '-][a-zA-Z]+)*");
	const std::array<std::string_view, 7> STAFF_PREFIXES = { "admin", "administrator", "accountmanager", "cm", "gamemaster", "gm", "god" };

	const std::string MENU = "Say 'character' to create a character, 'delete' to delete one, or 'password' to change your password. Say 'cancel' at any time to start over.";

	bool validPassword(const std::string &password) {
		return password.size() >= 8 && password.size() <= 128 && password.find_first_of(std::string_view("\0\r\n", 3)) == std::string::npos;
	}

	bool validCharacterName(const std::string &name) {
		if (name.size() < 4 || name.size() > 29 || !std::regex_match(name, CHARACTER_NAME)) {
			return false;
		}
		const auto lower = asLowerCaseString(name);
		const auto prefix = lower.substr(0, lower.find(' '));
		return lower != asLowerCaseString(std::string(AccountManager::NAME)) && std::ranges::find(STAFF_PREFIXES, prefix) == STAFF_PREFIXES.end();
	}

	std::string hashPassword(const std::string &password) {
		std::array<uint8_t, 16> salt {};
		std::random_device random;
		for (auto &byte : salt) {
			byte = static_cast<uint8_t>(random());
		}
		std::array<char, 255> encoded {};
		// Same Argon2id parameters as account_manager/storage.py.
		if (argon2id_hash_encoded(2, 65536, 2, password.data(), password.size(), salt.data(), salt.size(), 32, encoded.data(), encoded.size()) != ARGON2_OK) {
			return {};
		}
		return encoded.data();
	}

	bool exists(const std::string &query) {
		return g_database().storeQuery(query) != nullptr;
	}

	std::string vocationName(uint16_t id) {
		const auto &vocation = g_vocations().getVocation(id);
		return vocation ? vocation->getVocName() : std::string();
	}

	std::string vocationQuestion() {
		std::vector<std::string> names;
		for (const auto id : START_VOCATIONS) {
			if (auto name = vocationName(id); !name.empty()) {
				names.emplace_back(fmt::format("'{}'", asLowerCaseString(name)));
			}
		}
		return fmt::format("What do you want to be: {}?", fmt::join(names, ", "));
	}
}

bool AccountManager::isManagerName(const std::string &name) {
	return asLowerCaseString(name) == asLowerCaseString(std::string(NAME));
}

uint32_t AccountManager::nextCreatureId() {
	// GUID-based player IDs start at Player::getFirstID(); 16 million IDs below
	// the end of the range are reserved for Account Managers. Dispatcher thread only.
	constexpr uint32_t reserved = 0x01000000;
	static uint32_t next = Player::getLastID() - 1;
	if (next <= Player::getLastID() - reserved) {
		next = Player::getLastID() - 1;
	}
	return next--;
}

AccountManager::AccountManager(uint32_t accountId, bool newAccount) :
	accountId(accountId), creatingAccount(newAccount), step(newAccount ? Step::Start : Step::Menu) { }

void AccountManager::greet(const std::shared_ptr<Player> &player) const {
	using namespace account_manager_rules;
	player->sendTextMessage(MESSAGE_LOOK, "Account Manager: Welcome! Type your answers in the Local Chat channel. Nobody else can see what you type here.");
	player->sendTextMessage(MESSAGE_LOOK, creatingAccount ? "Account Manager: Say 'account' to create a new account." : "Account Manager: " + MENU);
}

void AccountManager::onSay(const std::shared_ptr<Player> &player, const std::string &text) {
	std::string trimmed = text;
	trimString(trimmed);
	if (trimmed.empty()) {
		return;
	}
	const auto keyword = asLowerCaseString(trimmed);
	const auto reply = creatingAccount ? handleNewAccount(trimmed, keyword) : handleAccount(trimmed, keyword);
	player->sendTextMessage(MESSAGE_LOOK, "Account Manager: " + reply);
}

void AccountManager::reset(Step next) {
	step = next;
	pendingName.clear();
	pendingPassword.clear();
}

std::string AccountManager::handleNewAccount(const std::string &text, const std::string &keyword) {
	using namespace account_manager_rules;
	if (keyword == "cancel") {
		reset(Step::Start);
		return "Say 'account' to create a new account.";
	}

	auto &db = g_database();
	switch (step) {
		case Step::Start:
			if (keyword != "account") {
				return "Say 'account' to create a new account.";
			}
			step = Step::NewPassword;
			return "What would you like your password to be? Use 8 to 128 characters.";

		case Step::NewPassword:
			if (!validPassword(text)) {
				return "Your password must have 8 to 128 characters. Please choose another one.";
			}
			pendingPassword = text;
			step = Step::NewPasswordRepeat;
			return "Please say the same password again to confirm it.";

		case Step::NewPasswordRepeat:
			if (text != pendingPassword) {
				pendingPassword.clear();
				step = Step::NewPassword;
				return "The passwords do not match. What would you like your password to be?";
			}
			step = Step::NewAccountName;
			return "What would you like your account name to be? Use 3 to 32 letters, digits, hyphens or underscores.";

		case Step::NewAccountName:
			if (!std::regex_match(text, ACCOUNT_NAME)) {
				return "Your account name must have 3 to 32 letters, digits, hyphens or underscores, starting with a letter or digit.";
			}
			if (keyword == asLowerCaseString(pendingPassword)) {
				return "Your account name cannot be the same as your password. Please choose another one.";
			}
			if (exists(fmt::format("SELECT 1 FROM `accounts` WHERE `name` = {}", db.escapeString(text)))) {
				return "That account name is already taken. Please choose another one.";
			}
			pendingName = text;
			step = Step::NewAccountNameConfirm;
			return fmt::format("'{}', are you sure? Say 'yes' or 'no'.", pendingName);

		case Step::NewAccountNameConfirm: {
			if (keyword == "no") {
				step = Step::NewAccountName;
				return "What would you like your account name to be, then?";
			}
			if (keyword != "yes") {
				return "Please say 'yes' or 'no'.";
			}
			const auto hash = hashPassword(pendingPassword);
			if (hash.empty()) {
				reset(Step::Start);
				return "Your account could not be created. Please say 'account' to try again.";
			}
			const auto escapedName = db.escapeString(pendingName);
			const auto result = db.storeQuery(fmt::format(
				"INSERT INTO `accounts` (`name`, `email`, `password`, `creation`) "
				"SELECT {0}, '', {1}, {2} WHERE NOT EXISTS (SELECT 1 FROM `accounts` WHERE `name` = {0}) RETURNING `id`",
				escapedName, db.escapeString(hash), time(nullptr)
			));
			if (!result) {
				step = Step::NewAccountName;
				return "That account name is no longer available. Please choose another one.";
			}
			accountId = result->getNumber<uint32_t>("id");
			creatingAccount = false;
			const auto created = pendingName;
			reset(Step::Menu);
			return fmt::format("Your account '{}' has been created. Remember your account name and password, you need them to log in. {}", created, MENU);
		}

		default:
			reset(Step::Start);
			return "Say 'account' to create a new account.";
	}
}

std::string AccountManager::handleAccount(const std::string &text, const std::string &keyword) {
	using namespace account_manager_rules;
	if (keyword == "cancel" || (step == Step::Menu && keyword == "account")) {
		reset(Step::Menu);
		return MENU;
	}

	auto &db = g_database();
	switch (step) {
		case Step::Menu:
			if (keyword == "character") {
				const auto count = db.storeQuery(fmt::format("SELECT count(*) AS `total` FROM `players` WHERE `account_id` = {}", accountId));
				if (count && count->getNumber<uint32_t>("total") >= MAX_CHARACTERS) {
					return fmt::format("Your account already has {} characters. Say 'delete' to delete one first.", MAX_CHARACTERS);
				}
				step = Step::CharacterName;
				return "What would you like as your character's name?";
			}
			if (keyword == "delete") {
				step = Step::DeleteName;
				return "Which character would you like to delete?";
			}
			if (keyword == "password") {
				step = Step::Password;
				return "What would you like your new password to be? Use 8 to 128 characters.";
			}
			return MENU;

		case Step::CharacterName:
			if (!validCharacterName(text)) {
				return "Use a fantasy name of 4 to 29 letters, with single spaces, hyphens or apostrophes. Please choose another one.";
			}
			if (exists(fmt::format("SELECT 1 FROM `players` WHERE `name` = {}", db.escapeString(text)))) {
				return "A character with that name already exists. Please choose another one.";
			}
			pendingName = text;
			step = Step::CharacterNameConfirm;
			return fmt::format("'{}', are you sure? Say 'yes' or 'no'.", pendingName);

		case Step::CharacterNameConfirm:
			if (keyword == "no") {
				step = Step::CharacterName;
				return "What else would you like to name your character?";
			}
			if (keyword != "yes") {
				return "Please say 'yes' or 'no'.";
			}
			step = Step::CharacterSex;
			return "Should your character be 'male' or 'female'?";

		case Step::CharacterSex:
			if (keyword != "male" && keyword != "female") {
				return "Please say 'male' or 'female'.";
			}
			pendingSex = keyword == "male" ? PLAYERSEX_MALE : PLAYERSEX_FEMALE;
			step = Step::CharacterVocation;
			return vocationQuestion();

		case Step::CharacterVocation:
			for (const auto id : START_VOCATIONS) {
				if (const auto name = vocationName(id); !name.empty() && keyword == asLowerCaseString(name)) {
					pendingVocation = id;
					step = Step::CharacterVocationConfirm;
					return fmt::format("So you would like to be a {}. Are you sure? Say 'yes' or 'no'.", name);
				}
			}
			return "I don't know that vocation. " + vocationQuestion();

		case Step::CharacterVocationConfirm: {
			if (keyword == "no") {
				step = Step::CharacterVocation;
				return vocationQuestion();
			}
			if (keyword != "yes") {
				return "Please say 'yes' or 'no'.";
			}
			const auto town = db.storeQuery(
				"SELECT `id` FROM `towns` WHERE `posx` > 0 AND `posy` > 0 "
				"ORDER BY CASE WHEN `name` = 'Thais' COLLATE NOCASE THEN 0 ELSE 1 END, `id` LIMIT 1"
			);
			if (!town) {
				reset(Step::Menu);
				return "No starting town is available. Please contact the administrator.";
			}
			const auto escapedName = db.escapeString(pendingName);
			const auto created = db.storeQuery(fmt::format(
				"INSERT INTO `players` (`name`, `account_id`, `level`, `vocation`, `experience`, `health`, `healthmax`, `mana`, `manamax`, "
				"`soul`, `cap`, `town_id`, `conditions`, `sex`, `looktype`, `lookhead`, `lookbody`, `looklegs`, `lookfeet`) "
				"SELECT {0}, {1}, 8, {2}, 4200, 185, 185, 90, 90, 100, 470, {3}, X'', {4}, {5}, 78, 106, 116, 95 "
				"WHERE NOT EXISTS (SELECT 1 FROM `players` WHERE `name` = {0}) "
				"AND (SELECT count(*) FROM `players` WHERE `account_id` = {1}) < {6} RETURNING `id`",
				escapedName, accountId, pendingVocation, town->getNumber<uint32_t>("id"), pendingSex,
				pendingSex == PLAYERSEX_MALE ? 128 : 136, MAX_CHARACTERS
			));
			const auto name = pendingName;
			reset(Step::Menu);
			if (!created) {
				return "Your character could not be created. The name may have just been taken. " + MENU;
			}
			return fmt::format("Your character '{}' has been created. Log out and log in again to select it. {}", name, MENU);
		}

		case Step::DeleteName:
			pendingName = text;
			step = Step::DeleteConfirm;
			return fmt::format("Do you really want to delete the character '{}'? It will be deleted in 7 days. Say 'yes' or 'no'.", pendingName);

		case Step::DeleteConfirm: {
			if (keyword != "yes" && keyword != "no") {
				return "Please say 'yes' or 'no'.";
			}
			const auto name = pendingName;
			reset(Step::Menu);
			if (keyword == "no") {
				return "Then not. " + MENU;
			}
			const auto deleted = db.storeQuery(fmt::format(
				"UPDATE `players` SET `deletion` = {} WHERE `name` = {} AND `account_id` = {} AND `deletion` = 0 "
				"AND NOT EXISTS (SELECT 1 FROM `players_online` WHERE `player_id` = `players`.`id`) RETURNING `id`",
				time(nullptr) + DELETION_DELAY, db.escapeString(name), accountId
			));
			if (!deleted) {
				return "That character does not belong to your account, is online, or is already scheduled for deletion. " + MENU;
			}
			return fmt::format("'{}' will be deleted in 7 days. You can restore it from the account website before then. {}", name, MENU);
		}

		case Step::Password:
			if (!validPassword(text)) {
				return "Your password must have 8 to 128 characters. Please choose another one.";
			}
			pendingPassword = text;
			step = Step::PasswordRepeat;
			return "Please say the same password again to confirm it.";

		case Step::PasswordRepeat: {
			if (text != pendingPassword) {
				reset(Step::Password);
				return "The passwords do not match. What would you like your new password to be?";
			}
			const auto hash = hashPassword(pendingPassword);
			reset(Step::Menu);
			const bool changed = !hash.empty() && DBTransaction::executeWithinTransactionRollbackOnFailure([&] {
				return g_database().executeQuery(fmt::format("UPDATE `accounts` SET `password` = {} WHERE `id` = {}", g_database().escapeString(hash), accountId))
					&& g_database().executeQuery(fmt::format("DELETE FROM `account_sessions` WHERE `account_id` = {}", accountId));
			});
			return changed ? "Your password has been changed. Use it the next time you log in. " + MENU : "Your password could not be changed. Please try again. " + MENU;
		}

		default:
			reset(Step::Menu);
			return MENU;
	}
}
