-- Gives every player who is online 15 Tibia Coins and 15 crystal coins each
-- time the timer fires. Change ZATHROTH_ONLINE_REWARD_MINUTES to 30 for a
-- shorter wait. Tibia Coins belong to the account, so they are given once per
-- account even when several of its characters are online; crystal coins go to
-- every character. A character without room for the coins gets their gold
-- value in the bank instead.
ZATHROTH_ONLINE_REWARD_MINUTES = 60

local TIBIA_COINS = 15
local CRYSTAL_COINS = 15
local CRYSTAL_COIN_ID = 3043
local CRYSTAL_COIN_WORTH = 10000

local reward = GlobalEvent("ZathrothOnlineReward")

function reward.onThink(interval)
	local paidAccounts = {}
	for _, player in ipairs(Game.getPlayers()) do
		-- The shared 1/1 Account Manager is a template character, not a player.
		if player:getName() ~= "Account Manager" then
			local accountId = player:getAccountId()
			local coins = 0
			if not paidAccounts[accountId] and player:addTransferableCoins(TIBIA_COINS) then
				paidAccounts[accountId] = true
				coins = TIBIA_COINS
			end

			local item = Game.createItem(CRYSTAL_COIN_ID, CRYSTAL_COINS)
			local stored = item and player:addItemEx(item, false) == RETURNVALUE_NOERROR
			if not stored then
				if item then
					item:remove()
				end
				player:setBankBalance(player:getBankBalance() + CRYSTAL_COINS * CRYSTAL_COIN_WORTH)
			end

			local parts = {}
			if coins > 0 then
				parts[#parts + 1] = string.format("%d Tibia Coins", coins)
			end
			parts[#parts + 1] = string.format(stored and "%d crystal coins" or "%d crystal coins (you could not carry them, so their value was paid into your bank)", CRYSTAL_COINS)
			player:sendTextMessage(MESSAGE_EVENT_ADVANCE, "Online reward: you received " .. table.concat(parts, " and ") .. ". Thank you for playing ZATHROTH!")
		end
	end
	logger.info("[ZathrothOnlineReward] rewarded {} online players", #Game.getPlayers())
	return true
end

reward:interval(ZATHROTH_ONLINE_REWARD_MINUTES * 60 * 1000)
reward:register()
