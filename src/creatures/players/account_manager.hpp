/**
 * ZATHROTH - In-game Account Manager
 * License: GPL-2.0 (see LICENSE)
 */

#pragma once

class Player;

// The 1/1 "Account Manager" character: a temporary, never-saved player that
// creates accounts and manages characters through chat, like 8.60 servers.
class AccountManager {
public:
	static constexpr std::string_view NAME = "Account Manager";

	static bool isManagerName(const std::string &name);
	// Every Account Manager shares the template's GUID, so creature IDs cannot
	// come from it. These come from the top of the player ID range instead.
	static uint32_t nextCreatureId();

	// newAccount: logged in through the shared 1/1 account, so the dialog
	// starts by creating an account. Otherwise it manages accountId.
	AccountManager(uint32_t accountId, bool newAccount);

	void greet(const std::shared_ptr<Player> &player) const;
	void onSay(const std::shared_ptr<Player> &player, const std::string &text);

private:
	enum class Step : uint8_t {
		Start,
		NewPassword,
		NewPasswordRepeat,
		NewAccountName,
		NewAccountNameConfirm,
		Menu,
		CharacterName,
		CharacterNameConfirm,
		CharacterSex,
		CharacterVocation,
		CharacterVocationConfirm,
		DeleteName,
		DeleteConfirm,
		Password,
		PasswordRepeat,
	};

	std::string handleNewAccount(const std::string &text, const std::string &keyword);
	std::string handleAccount(const std::string &text, const std::string &keyword);
	void reset(Step next);

	uint32_t accountId;
	bool creatingAccount;
	Step step;
	std::string pendingName;
	std::string pendingPassword;
	uint8_t pendingSex = 0;
	uint16_t pendingVocation = 0;
};
