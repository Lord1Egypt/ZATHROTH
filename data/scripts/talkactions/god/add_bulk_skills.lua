-- Raises every skill and the magic level of an online player by the same
-- number of levels. Levels are set directly: gods do not gain skill tries or
-- mana, and large try counts do not survive the skill-gain event.
local MAX_LEVELS = 1000
local MAX_SKILL_LEVEL = 65535

local skills = {
	{ id = SKILL_FIST, name = "fist" },
	{ id = SKILL_CLUB, name = "club" },
	{ id = SKILL_SWORD, name = "sword" },
	{ id = SKILL_AXE, name = "axe" },
	{ id = SKILL_DISTANCE, name = "distance" },
	{ id = SKILL_SHIELD, name = "shielding" },
	{ id = SKILL_FISHING, name = "fishing" },
}

local addBulkSkills = TalkAction("/addbulkskills")

function addBulkSkills.onSay(player, words, param)
	logCommand(player, words, param)

	local name, levels = param:match("^%s*(.-)%s*,?%s*(%d+)%s*$")
	levels = tonumber(levels)
	local target = name and name ~= "" and Player(name)
	if not target or not levels or levels < 1 or levels > MAX_LEVELS then
		player:sendCancelMessage(string.format("Usage: /addbulkskills <online player name> <levels from 1 to %d>", MAX_LEVELS))
		return true
	end

	local summary = {}
	for _, skill in ipairs(skills) do
		target:setSkillLevel(skill.id, math.min(target:getSkillLevel(skill.id) + levels, MAX_SKILL_LEVEL))
		summary[#summary + 1] = string.format("%s %d", skill.name, target:getSkillLevel(skill.id))
	end
	target:setMagicLevel(math.min(target:getBaseMagicLevel() + levels, MAX_SKILL_LEVEL))
	summary[#summary + 1] = string.format("magic %d", target:getBaseMagicLevel())

	local result = table.concat(summary, ", ")
	target:sendTextMessage(MESSAGE_EVENT_ADVANCE, string.format("%s raised all your skills by %d: %s.", player:getName(), levels, result))
	if target ~= player then
		player:sendTextMessage(MESSAGE_EVENT_ADVANCE, string.format("Raised all skills of %s by %d: %s.", target:getName(), levels, result))
	end
	return true
end

addBulkSkills:separator(" ")
addBulkSkills:setDescription("[Usage]: /addbulkskills <player name> <levels>, raises every skill and the magic level")
addBulkSkills:groupType("god")
addBulkSkills:register()
