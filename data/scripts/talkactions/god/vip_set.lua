-- Gives an online player the ZATHROTH VIP set: golden pieces with raised
-- armor and defense, nearly weightless, in a golden backpack.
local GOLDEN_BACKPACK = 2871

local pieces = {
	{ id = 3365, name = "ZATHROTH VIP helmet", attribute = ITEM_ATTRIBUTE_ARMOR, value = 20 },
	{ id = 3360, name = "ZATHROTH VIP armor", attribute = ITEM_ATTRIBUTE_ARMOR, value = 30 },
	{ id = 3364, name = "ZATHROTH VIP legs", attribute = ITEM_ATTRIBUTE_ARMOR, value = 20 },
	{ id = 3555, name = "ZATHROTH VIP boots", attribute = ITEM_ATTRIBUTE_ARMOR, value = 10 },
	{ id = 3422, name = "ZATHROTH VIP shield", attribute = ITEM_ATTRIBUTE_DEFENSE, value = 60 },
}

local vipSet = TalkAction("/vipset")

function vipSet.onSay(player, words, param)
	logCommand(player, words, param)

	local target = param ~= "" and Player(param:trim()) or player
	if not target then
		player:sendCancelMessage("Usage: /vipset [online player name]")
		return true
	end

	local backpack = Game.createItem(GOLDEN_BACKPACK, 1)
	backpack:setAttribute(ITEM_ATTRIBUTE_NAME, "ZATHROTH VIP backpack")
	local description = "ZATHROTH VIP set of " .. target:getName() .. "."
	for _, piece in ipairs(pieces) do
		local item = backpack:addItem(piece.id, 1)
		item:setAttribute(ITEM_ATTRIBUTE_NAME, piece.name)
		item:setAttribute(ITEM_ATTRIBUTE_DESCRIPTION, description)
		item:setAttribute(piece.attribute, piece.value)
		item:setAttribute(ITEM_ATTRIBUTE_WEIGHT, 100)
	end

	if target:addItemEx(backpack) ~= RETURNVALUE_NOERROR then
		local inbox = target:getStoreInbox()
		if not inbox or not backpack:moveTo(inbox) then
			backpack:remove()
			player:sendCancelMessage(target:getName() .. " has no room for the VIP set.")
			return true
		end
		target:sendTextMessage(MESSAGE_EVENT_ADVANCE, "Your ZATHROTH VIP set is in your store inbox.")
	else
		target:sendTextMessage(MESSAGE_EVENT_ADVANCE, "You received the ZATHROTH VIP set.")
	end
	target:getPosition():sendMagicEffect(CONST_ME_HOLYAREA)
	if target ~= player then
		player:sendTextMessage(MESSAGE_EVENT_ADVANCE, "Gave the ZATHROTH VIP set to " .. target:getName() .. ".")
	end
	return true
end

vipSet:separator(" ")
vipSet:groupType("god")
vipSet:register()
