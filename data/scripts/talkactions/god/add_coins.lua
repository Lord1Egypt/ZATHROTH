local addCoins = TalkAction("/addcoins")

function addCoins.onSay(player, words, param)
	logCommand(player, words, param)

	local split = param:split(",")
	local target = split[1] and Player(split[1]:trim())
	local amount = tonumber(split[2] and split[2]:trim())
	if not target or not amount or amount < 1 or amount ~= math.floor(amount) or amount > 100000000 then
		player:sendCancelMessage("Usage: /addcoins <online player name>, <amount from 1 to 100000000>")
		return true
	end

	if not target:addTibiaCoins(amount) then
		player:sendCancelMessage("Adding Tibia Coins failed. See the server log.")
		return true
	end

	target:sendTextMessage(MESSAGE_EVENT_ADVANCE, string.format("%s has added %d Tibia Coins to your account.", player:getName(), amount))
	player:sendTextMessage(MESSAGE_EVENT_ADVANCE, string.format("Added %d Tibia Coins to %s. The account now has %d.", amount, target:getName(), target:getTibiaCoins()))
	return true
end

addCoins:separator(" ")
addCoins:setDescription("[Usage]: /addcoins <player name>, <amount>, adds Tibia Coins")
addCoins:groupType("god")
addCoins:register()
