local area = createCombatArea({
	{ 1, 1, 1 },
	{ 1, 3, 1 },
	{ 1, 1, 1 },
})

local combat = Combat()
combat:setParameter(COMBAT_PARAM_TYPE, COMBAT_PHYSICALDAMAGE)
combat:setParameter(COMBAT_PARAM_EFFECT, CONST_ME_EXPLOSIONAREA)
combat:setParameter(COMBAT_PARAM_DISTANCEEFFECT, CONST_ANI_BURSTARROW)
combat:setParameter(COMBAT_PARAM_BLOCKARMOR, true)
combat:setFormula(COMBAT_FORMULA_SKILL, 0, 0, 1, 0)
combat:setParameter(COMBAT_PARAM_IMPACTSOUND, SOUND_EFFECT_TYPE_BURST_ARROW_EFFECT)
combat:setParameter(COMBAT_PARAM_CASTSOUND, SOUND_EFFECT_TYPE_DIST_ATK_BOW)
combat:setArea(area)

-- ZATHROTH VIP arrows: an inferno of fire over 9x9 tiles that leaves every
-- target burning.
local burning = Condition(CONDITION_FIRE)
burning:setParameter(CONDITION_PARAM_DELAYED, true)
burning:addDamage(10, 2000, -150)

local vipCombat = Combat()
vipCombat:setParameter(COMBAT_PARAM_TYPE, COMBAT_FIREDAMAGE)
vipCombat:setParameter(COMBAT_PARAM_EFFECT, CONST_ME_FIREAREA)
vipCombat:setParameter(COMBAT_PARAM_DISTANCEEFFECT, CONST_ANI_FIRE)
vipCombat:setFormula(COMBAT_FORMULA_SKILL, 0, 0, 1.8, 0)
vipCombat:setParameter(COMBAT_PARAM_IMPACTSOUND, SOUND_EFFECT_TYPE_BURST_ARROW_EFFECT)
vipCombat:setParameter(COMBAT_PARAM_CASTSOUND, SOUND_EFFECT_TYPE_DIST_ATK_BOW)
vipCombat:setArea(createCombatArea(ZATHROTH_VIP_AMMO_AREA))
vipCombat:addCondition(burning)

local burstArrow = Weapon(WEAPON_AMMO)

burstArrow.onUseWeapon = function(player, variant)
	if player:getSkull() == SKULL_BLACK then
		return false
	end

	if zathrothFiredAmmoActionId(player, 3449) == ZATHROTH_VIP_AMMO_ACTION_ID then
		local target = Creature(variant:getNumber())
		if target then
			target:getPosition():sendMagicEffect(CONST_ME_EXPLOSIONHIT)
		end
		zathrothVipAmmoHeal(player)
		return vipCombat:execute(player, variant)
	end
	return combat:execute(player, variant)
end

burstArrow:id(3449)
burstArrow:attack(27)
burstArrow:action("removecount")
burstArrow:ammoType("arrow")
burstArrow:shootType(CONST_ANI_BURSTARROW)
burstArrow:maxHitChance(100)
burstArrow:register()
