-- ZATHROTH VIP ammunition carries this action ID. Burst arrows and power
-- bolts with it explode over a 9x9 area; without it they behave normally.
ZATHROTH_VIP_AMMO_ACTION_ID = 61530

-- 9x9 area centred on the target.
ZATHROTH_VIP_AMMO_AREA = {
	{ 1, 1, 1, 1, 1, 1, 1, 1, 1 },
	{ 1, 1, 1, 1, 1, 1, 1, 1, 1 },
	{ 1, 1, 1, 1, 1, 1, 1, 1, 1 },
	{ 1, 1, 1, 1, 1, 1, 1, 1, 1 },
	{ 1, 1, 1, 1, 3, 1, 1, 1, 1 },
	{ 1, 1, 1, 1, 1, 1, 1, 1, 1 },
	{ 1, 1, 1, 1, 1, 1, 1, 1, 1 },
	{ 1, 1, 1, 1, 1, 1, 1, 1, 1 },
	{ 1, 1, 1, 1, 1, 1, 1, 1, 1 },
}

-- Bows and crossbows fire the first item in the quiver (right hand) whose
-- ammunition type matches and whose level requirement the player meets.
function isZathrothVipAmmo(player, itemId)
	local quiver = player:getSlotItem(CONST_SLOT_RIGHT)
	if not quiver or not quiver:isContainer() then
		return false
	end

	local ammoType = ItemType(itemId):getAmmoType()
	for _, item in ipairs(quiver:getItems()) do
		local itemType = ItemType(item:getId())
		if itemType:getAmmoType() == ammoType and player:getLevel() >= itemType:getRequiredLevel() then
			return item:getId() == itemId and item:getActionId() == ZATHROTH_VIP_AMMO_ACTION_ID
		end
	end
	return false
end
