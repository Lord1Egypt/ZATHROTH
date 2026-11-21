-- Power bolts hit one target. ZATHROTH VIP bolts call a thunderstorm of
-- energy over 9x9 tiles instead and leave every target electrified.
local combat = Combat()
combat:setParameter(COMBAT_PARAM_TYPE, COMBAT_PHYSICALDAMAGE)
combat:setParameter(COMBAT_PARAM_DISTANCEEFFECT, CONST_ANI_POWERBOLT)
combat:setParameter(COMBAT_PARAM_BLOCKARMOR, true)
combat:setFormula(COMBAT_FORMULA_SKILL, 0, 0, 1, 0)

local electrified = Condition(CONDITION_ENERGY)
electrified:setParameter(CONDITION_PARAM_DELAYED, true)
electrified:addDamage(10, 2000, -150)

local vipCombat = Combat()
vipCombat:setParameter(COMBAT_PARAM_TYPE, COMBAT_ENERGYDAMAGE)
vipCombat:setParameter(COMBAT_PARAM_EFFECT, CONST_ME_ENERGYAREA)
vipCombat:setParameter(COMBAT_PARAM_DISTANCEEFFECT, CONST_ANI_ENERGYBALL)
vipCombat:setFormula(COMBAT_FORMULA_SKILL, 0, 0, 1.8, 0)
vipCombat:setArea(createCombatArea(ZATHROTH_VIP_AMMO_AREA))
vipCombat:addCondition(electrified)

local powerBolt = Weapon(WEAPON_AMMO)

powerBolt.onUseWeapon = function(player, variant)
	if player:getSkull() == SKULL_BLACK then
		return false
	end

	if zathrothFiredAmmoActionId(player, 3450) == ZATHROTH_VIP_AMMO_ACTION_ID then
		local target = Creature(variant:getNumber())
		if target then
			target:getPosition():sendMagicEffect(CONST_ME_BIGCLOUDS)
		end
		zathrothVipAmmoHeal(player)
		return vipCombat:execute(player, variant)
	end
	return combat:execute(player, variant)
end

powerBolt:id(3450)
powerBolt:attack(40)
powerBolt:action("removecount")
powerBolt:ammoType("bolt")
powerBolt:shootType(CONST_ANI_POWERBOLT)
powerBolt:maxHitChance(91)
powerBolt:register()
