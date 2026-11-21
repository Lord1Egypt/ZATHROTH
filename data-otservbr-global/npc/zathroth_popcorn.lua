-- ZATHROTH Popcorn: sells experience for gold and popcorn. Placed next to the
-- temple of every town by globalevents/zathroth_popcorn_spawn.lua.
local internalNpcName = "Zathroth Popcorn"
local npcType = Game.createNpcType(internalNpcName)
local npcConfig = {}

npcConfig.name = internalNpcName
npcConfig.description = "the experience and popcorn merchant"

npcConfig.health = 100
npcConfig.maxHealth = npcConfig.health
npcConfig.walkInterval = 0
npcConfig.walkRadius = 0

npcConfig.outfit = {
	lookType = 128,
	lookHead = 79,
	lookBody = 94,
	lookLegs = 114,
	lookFeet = 79,
	lookAddons = 3,
}

npcConfig.flags = {
	floorchange = false,
	profession = "trader",
}

local EXP_PER_GOLD = 2
local MAX_EXPERIENCE = 1000000000000
local POPCORN_ITEM = 3597 -- corncob; the client has no popcorn sprite
local POPCORN_PRICE = 25

local TOPIC_EXPERIENCE = 1
local TOPIC_ALL_MONEY = 2
local TOPIC_POPCORN = 3

local keywordHandler = KeywordHandler:new()
local npcHandler = NpcHandler:new(keywordHandler)
local pending = {}

npcType.onThink = function(npc, interval)
	npcHandler:onThink(npc, interval)
end

npcType.onAppear = function(npc, creature)
	npcHandler:onAppear(npc, creature)
end

npcType.onDisappear = function(npc, creature)
	npcHandler:onDisappear(npc, creature)
end

npcType.onMove = function(npc, creature, fromPosition, toPosition)
	npcHandler:onMove(npc, creature, fromPosition, toPosition)
end

npcType.onSay = function(npc, creature, type, message)
	npcHandler:onSay(npc, creature, type, message)
end

npcType.onCloseChannel = function(npc, creature)
	npcHandler:onCloseChannel(npc, creature)
end

local function givePopcorn(player, count)
	local popcorn = Game.createItem(POPCORN_ITEM, count)
	popcorn:setAttribute(ITEM_ATTRIBUTE_NAME, "ZATHROTH popcorn")
	popcorn:setAttribute(ITEM_ATTRIBUTE_PLURALNAME, "ZATHROTH popcorn")
	popcorn:setAttribute(ITEM_ATTRIBUTE_DESCRIPTION, "Fresh popcorn for watching the show.")
	if player:addItemEx(popcorn, true) ~= RETURNVALUE_NOERROR then
		popcorn:remove()
		return false
	end
	return true
end

local function deliverExperience(npc, player, experience)
	player:addExperience(experience, true)
	player:getPosition():sendMagicEffect(CONST_ME_FIREWORK_YELLOW)
	local gift = givePopcorn(player, 1) and " Here is some popcorn as a gift!" or ""
	npcHandler:say(string.format("Done, %s experience is yours.%s", FormatNumber(experience), gift), npc, player)
end

local function creatureSayCallback(npc, creature, type, message)
	local player = Player(creature)
	if not player or not npcHandler:checkInteraction(npc, creature) then
		return false
	end

	local playerId = player:getId()
	local text = message:lower():gsub(",", ""):match("^%s*(.-)%s*$")
	local topic = npcHandler:getTopic(playerId)

	if text == "yes" and topic ~= 0 then
		npcHandler:setTopic(playerId, 0)
		if topic == TOPIC_EXPERIENCE then
			local order = pending[playerId]
			if not player:removeMoneyBank(order.price) then
				npcHandler:say("You don't have enough gold in your backpack and bank.", npc, creature)
				return true
			end
			deliverExperience(npc, player, order.experience)
		elseif topic == TOPIC_ALL_MONEY then
			local money = player:getMoney()
			if money <= 0 or not player:removeMoney(money) then
				npcHandler:say("You have no money in your backpack.", npc, creature)
				return true
			end
			deliverExperience(npc, player, money * EXP_PER_GOLD)
		elseif topic == TOPIC_POPCORN then
			if not player:removeMoneyBank(POPCORN_PRICE) then
				npcHandler:say("You don't have enough gold.", npc, creature)
				return true
			end
			if not givePopcorn(player, 1) then
				player:setBankBalance(player:getBankBalance() + POPCORN_PRICE)
				npcHandler:say("You have no room for popcorn, so the gold went to your bank.", npc, creature)
				return true
			end
			npcHandler:say("Enjoy the show!", npc, creature)
		end
		return true
	end

	if text == "no" and topic ~= 0 then
		npcHandler:setTopic(playerId, 0)
		npcHandler:say("Maybe next time.", npc, creature)
		return true
	end

	local experience = tonumber(text:match("^(%d+)$"))
	if experience then
		if experience < EXP_PER_GOLD or experience > MAX_EXPERIENCE then
			npcHandler:say(string.format("Tell me an amount from %d to %s experience.", EXP_PER_GOLD, FormatNumber(MAX_EXPERIENCE)), npc, creature)
			return true
		end
		local price = math.ceil(experience / EXP_PER_GOLD)
		pending[playerId] = { experience = experience, price = price }
		npcHandler:setTopic(playerId, TOPIC_EXPERIENCE)
		npcHandler:say(string.format("%s experience costs %s gold, paid from your backpack and then your bank. Do you want it? {yes} or {no}", FormatNumber(experience), FormatNumber(price)), npc, creature)
	elseif text == "all" then
		local money = player:getMoney()
		if money <= 0 then
			npcHandler:say("You have no money in your backpack.", npc, creature)
			return true
		end
		npcHandler:setTopic(playerId, TOPIC_ALL_MONEY)
		npcHandler:say(string.format("I take all %s gold in your backpack and give you %s experience. Do you want it? {yes} or {no}", FormatNumber(money), FormatNumber(money * EXP_PER_GOLD)), npc, creature)
	elseif text == "exp" or text == "experience" then
		npcHandler:say(string.format("I sell %d experience for every gold coin. How much experience do you want? Tell me a number, like {10000000}, or say {all} to trade all the money in your backpack.", EXP_PER_GOLD), npc, creature)
	elseif text == "popcorn" then
		npcHandler:setTopic(playerId, TOPIC_POPCORN)
		npcHandler:say(string.format("A bag of popcorn costs %d gold. Do you want one? {yes} or {no}", POPCORN_PRICE), npc, creature)
	end
	return true
end

npcHandler:setMessage(MESSAGE_GREET, "Welcome, |PLAYERNAME|! I sell {experience} and {popcorn}. How much experience do you want? Tell me a number, or say {all}.")
npcHandler:setMessage(MESSAGE_FAREWELL, "Enjoy the show, |PLAYERNAME|!")
npcHandler:setCallback(CALLBACK_MESSAGE_DEFAULT, creatureSayCallback)
npcHandler:addModule(FocusModule:new(), npcConfig.name, true, true, true)

npcType:register(npcConfig)
