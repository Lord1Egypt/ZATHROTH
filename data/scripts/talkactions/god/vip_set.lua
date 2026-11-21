-- Gives an online player the ZATHROTH VIP set: golden armor pieces with
-- raised armor and defense, the strongest weapon of each kind with raised
-- attack, and exploding VIP arrows and bolts, all nearly weightless, in a
-- 100-slot VIP backpack. Worn VIP items grant the bonuses in
-- data/scripts/lib/zathroth_vip.lua. Gods ignore weapon level and vocation
-- requirements; other players still need them. Wand and rod damage comes
-- from the item itself. The changing backpack is not obtainable elsewhere;
-- items.xml gives it 100 slots.
local VIP_BACKPACK = 37536

local pieces = {
	{ id = 3365, name = "ZATHROTH VIP helmet", attributes = { [ITEM_ATTRIBUTE_ARMOR] = 20 } },
	{ id = 3360, name = "ZATHROTH VIP armor", attributes = { [ITEM_ATTRIBUTE_ARMOR] = 30 } },
	{ id = 3364, name = "ZATHROTH VIP legs", attributes = { [ITEM_ATTRIBUTE_ARMOR] = 20 } },
	{ id = 3555, name = "ZATHROTH VIP boots", attributes = { [ITEM_ATTRIBUTE_ARMOR] = 10 } },
	{ id = 3422, name = "ZATHROTH VIP shield", attributes = { [ITEM_ATTRIBUTE_DEFENSE] = 70 } },
	{ id = 28723, name = "ZATHROTH VIP sword", attributes = { [ITEM_ATTRIBUTE_ATTACK] = 90, [ITEM_ATTRIBUTE_DEFENSE] = 45 } },
	{ id = 36661, name = "ZATHROTH VIP axe", attributes = { [ITEM_ATTRIBUTE_ATTACK] = 90, [ITEM_ATTRIBUTE_DEFENSE] = 45 } },
	{ id = 7367, name = "ZATHROTH VIP spears", count = 100, attributes = { [ITEM_ATTRIBUTE_ATTACK] = 70 } },
	{ id = 43878, name = "ZATHROTH VIP bow", attributes = { [ITEM_ATTRIBUTE_ATTACK] = 20 } },
	{ id = 43880, name = "ZATHROTH VIP crossbow", attributes = { [ITEM_ATTRIBUTE_ATTACK] = 22 } },
	{ id = 43883, name = "ZATHROTH VIP wand" },
	{ id = 43886, name = "ZATHROTH VIP rod" },
}

-- Bows and crossbows take ammunition from a quiver in the right hand. Burst
-- arrows and power bolts with the VIP action ID explode over 9x9 tiles
-- (data/scripts/weapons/scripts/burst_arrow.lua and power_bolt.lua).
local QUIVER = { id = 35524, name = "ZATHROTH VIP quiver" }
local ammunition = {
	{ id = 3449, name = "ZATHROTH VIP inferno arrows", count = 100, actionId = ZATHROTH_VIP_AMMO_ACTION_ID, attributes = { [ITEM_ATTRIBUTE_ATTACK] = 80 } },
	{ id = 3450, name = "ZATHROTH VIP thunder bolts", count = 100, actionId = ZATHROTH_VIP_AMMO_ACTION_ID, attributes = { [ITEM_ATTRIBUTE_ATTACK] = 90 } },
}
-- Gods also get a god quiver with infinite god arrows and god bolts
-- (data/scripts/weapons/scripts/zathroth_god_ammo.lua). Wear it instead of the
-- VIP quiver to shoot them; their names come from items.xml.
local GOD_QUIVER = { id = 39150, name = "ZATHROTH god quiver" }
local godAmmunition = { ZATHROTH_GOD_ARROW, ZATHROTH_GOD_BOLT }

-- Items get their VIP weight before they enter a container: a container
-- keeps the weight its items had when they were added, so setting a light
-- weight afterwards would leave the set counted at the base weights.
local function createPiece(piece, description)
	local item = Game.createItem(piece.id, piece.count or 1)
	item:setAttribute(ITEM_ATTRIBUTE_NAME, piece.name)
	-- Stacks of more than one show the plural name.
	item:setAttribute(ITEM_ATTRIBUTE_PLURALNAME, piece.name)
	item:setAttribute(ITEM_ATTRIBUTE_DESCRIPTION, description)
	for attribute, value in pairs(piece.attributes or {}) do
		item:setAttribute(attribute, value)
	end
	if piece.actionId then
		item:setActionId(piece.actionId)
	end
	-- The weight is per piece: 1 oz for single items, 0.01 oz for stackables.
	item:setAttribute(ITEM_ATTRIBUTE_WEIGHT, piece.count and 1 or 100)
	return item
end

local vipSet = TalkAction("/vipset")

function vipSet.onSay(player, words, param)
	logCommand(player, words, param)

	local target = param ~= "" and Player(param:trim()) or player
	if not target then
		player:sendCancelMessage("Usage: /vipset [online player name]")
		return true
	end

	local backpack = Game.createItem(VIP_BACKPACK, 1)
	backpack:setAttribute(ITEM_ATTRIBUTE_NAME, "ZATHROTH VIP backpack")
	local description = "ZATHROTH VIP set of " .. target:getName() .. "."
	for _, piece in ipairs(pieces) do
		backpack:addItemEx(createPiece(piece, description))
	end
	local quiver = createPiece(QUIVER, description)
	for _, piece in ipairs(ammunition) do
		quiver:addItemEx(createPiece(piece, description))
	end
	backpack:addItemEx(quiver)
	if target:getGroup():getId() >= GROUP_TYPE_GOD then
		local godQuiver = createPiece(GOD_QUIVER, description)
		for _, itemId in ipairs(godAmmunition) do
			godQuiver:addItem(itemId, 100)
		end
		backpack:addItemEx(godQuiver)
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
vipSet:setDescription("[Usage]: /vipset [player name], gives the ZATHROTH VIP armor and weapon set")
vipSet:groupType("god")
vipSet:register()
