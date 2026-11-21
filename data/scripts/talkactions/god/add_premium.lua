local MAX_DAYS = 3650

local addPremium = TalkAction("/addpremium")

function addPremium.onSay(player, words, param)
	logCommand(player, words, param)

	-- Accepts "name, days" and "name days".
	local name, days = param:match("^%s*(.-)%s*,?%s*(%d+)%s*$")
	local target = name and name ~= "" and Player(name)
	days = tonumber(days)
	if not target or not days or days < 1 or days > MAX_DAYS then
		player:sendCancelMessage(string.format("Usage: /addpremium <online player name> <days from 1 to %d>", MAX_DAYS))
		return true
	end

	target:addPremiumDays(days)
	target:getPosition():sendMagicEffect(CONST_ME_HOLYAREA)
	target:sendTextMessage(MESSAGE_EVENT_ADVANCE, string.format("%s has added %d premium days to your account. You now have %d.", player:getName(), days, target:getPremiumDays()))
	if target ~= player then
		player:sendTextMessage(MESSAGE_EVENT_ADVANCE, string.format("Added %d premium days to %s. The account now has %d.", days, target:getName(), target:getPremiumDays()))
	end
	return true
end

addPremium:separator(" ")
addPremium:setDescription("[Usage]: /addpremium <player name> <days>, adds premium days to the player's account")
addPremium:groupType("god")
addPremium:register()
