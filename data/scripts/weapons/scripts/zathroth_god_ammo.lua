-- ZATHROTH god ammunition, usable only by gods and never used up (no
-- "removecount" action).
-- God arrows: sudden death over the 9x9 square around the target.
-- God bolts: a lightning storm like exevo gran mas vis over the spell's 6x6
-- circle around the target.
-- Every monster in the area dies in one shot.
local function isGod(player)
	return player:getGroup():getId() >= GROUP_TYPE_GOD
end

-- Combat callbacks are looked up by global name.
function zathrothOnGodAmmoTile(player, position)
	local tile = Tile(position)
	for _, creature in ipairs(tile and tile:getCreatures() or {}) do
		if creature:isMonster() then
			zathrothGodKill(player, creature)
		end
	end
end

local function godArea(effect, area)
	local combat = Combat()
	combat:setParameter(COMBAT_PARAM_EFFECT, effect)
	combat:setArea(createCombatArea(area))
	combat:setCallback(CALLBACK_PARAM_TARGETTILE, "zathrothOnGodAmmoTile")
	return combat
end

local deathArea = godArea(CONST_ME_MORTAREA, ZATHROTH_VIP_AMMO_AREA)
local storm = godArea(CONST_ME_BIGCLOUDS, AREA_CIRCLE6X6)

local godArrow = Weapon(WEAPON_AMMO)

godArrow.onUseWeapon = function(player, variant)
	local target = Creature(variant:getNumber())
	if not isGod(player) or not target or not target:isMonster() then
		return false
	end

	local position = target:getPosition()
	player:getPosition():sendDistanceEffect(position, CONST_ANI_SUDDENDEATH)
	return deathArea:execute(player, Variant(position))
end

godArrow:id(ZATHROTH_GOD_ARROW)
godArrow:attack(100)
godArrow:ammoType("arrow")
godArrow:shootType(CONST_ANI_SUDDENDEATH)
godArrow:maxHitChance(100)
godArrow:register()

local godBolt = Weapon(WEAPON_AMMO)

godBolt.onUseWeapon = function(player, variant)
	local target = Creature(variant:getNumber())
	if not isGod(player) or not target or not target:isMonster() then
		return false
	end

	local position = target:getPosition()
	player:getPosition():sendDistanceEffect(position, CONST_ANI_ENERGYBALL)
	position:sendMagicEffect(CONST_ME_ENERGYHIT)
	return storm:execute(player, Variant(position))
end

godBolt:id(ZATHROTH_GOD_BOLT)
godBolt:attack(100)
godBolt:ammoType("bolt")
godBolt:shootType(CONST_ANI_ENERGYBALL)
godBolt:maxHitChance(100)
godBolt:register()
