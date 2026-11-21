local MAX_LEVELS = 5000

local addLevel = TalkAction("/addlevel")

function addLevel.onSay(player, words, param)
	logCommand(player, words, param)

	-- Accepts "name, levels" and "name levels".
	local name, levels = param:match("^%s*(.-)%s*,?%s*(%d+)%s*$")
	local target = name and name ~= "" and Player(name)
	levels = tonumber(levels)
	if not target or not levels or levels < 1 or levels > MAX_LEVELS then
		player:sendCancelMessage(string.format("Usage: /addlevel <online player name> <levels from 1 to %d>", MAX_LEVELS))
		return true
	end

	local newLevel = target:getLevel() + levels
	target:addExperience(Game.getExperienceForLevel(newLevel) - target:getExperience(), true)
	target:getPosition():sendMagicEffect(CONST_ME_FIREWORK_YELLOW)
	if target ~= player then
		player:sendTextMessage(MESSAGE_EVENT_ADVANCE, string.format("%s is now level %d.", target:getName(), target:getLevel()))
	end
	return true
end

addLevel:separator(" ")
addLevel:setDescription("[Usage]: /addlevel <player name> <levels>, raises the character level")
addLevel:groupType("god")
addLevel:register()
