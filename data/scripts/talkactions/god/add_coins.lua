local addCoins = TalkAction("/addcoins")

function addCoins.onSay(player, words, param)
	logCommand(player, words, param)

	-- Accepts "name, amount" and "name amount".
	local name, amount = param:match("^%s*(.-)%s*,?%s*(%d+)%s*$")
	local target = name and name ~= "" and Player(name)
	amount = tonumber(amount)
	if not target or not amount or amount < 1 or amount > 100000000 then
		player:sendCancelMessage("Usage: /addcoins <online player name> <amount from 1 to 100000000>")
		return true
	end

	-- Store offers default to transferable coins, and the client checks the
	-- transferable balance before it lets a player buy, so add those.
	if not target:addTransferableCoins(amount) then
		player:sendCancelMessage("Adding Tibia Coins failed. See the server log.")
		return true
	end

	target:sendTextMessage(MESSAGE_EVENT_ADVANCE, string.format("%s has added %d Tibia Coins to your account.", player:getName(), amount))
	player:sendTextMessage(MESSAGE_EVENT_ADVANCE, string.format("Added %d Tibia Coins to %s. The account now has %d.", amount, target:getName(), target:getTransferableCoins() + target:getTibiaCoins()))
	return true
end

addCoins:separator(" ")
addCoins:setDescription("[Usage]: /addcoins <player name> <amount>, adds Tibia Coins")
addCoins:groupType("god")
addCoins:register()
