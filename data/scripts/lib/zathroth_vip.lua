-- ZATHROTH VIP ammunition carries this action ID. Burst arrows and power
-- bolts with it explode over a 9x9 area; without it they behave normally.
ZATHROTH_VIP_AMMO_ACTION_ID = 61530
-- God arrows and god bolts are their own item types: items.xml 25757 and
-- 25758, old diamond arrow and spectral bolt IDs not obtainable elsewhere.
-- Their weapon is data/scripts/weapons/scripts/zathroth_god_ammo.lua.
ZATHROTH_GOD_ARROW = 25757
ZATHROTH_GOD_BOLT = 25758

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
-- Returns the action ID of that item when it is itemId, else nil.
function zathrothFiredAmmoActionId(player, itemId)
	local quiver = player:getSlotItem(CONST_SLOT_RIGHT)
	if not quiver or not quiver:isContainer() then
		return nil
	end

	local ammoType = ItemType(itemId):getAmmoType()
	for _, item in ipairs(quiver:getItems()) do
		local itemType = ItemType(item:getId())
		if itemType:getAmmoType() == ammoType and player:getLevel() >= itemType:getRequiredLevel() then
			return item:getId() == itemId and item:getActionId() or nil
		end
	end
	return nil
end

-- Kills a monster outright. Undefined damage ignores armor, elements and
-- immunities; twice the maximum health stays clear of integer overflow when
-- damage buffs multiply it.
function zathrothGodKill(player, monster)
	local damage = -2 * monster:getMaxHealth()
	doTargetCombatHealth(player, monster, COMBAT_UNDEFINEDDAMAGE, damage, damage, CONST_ME_NONE, ORIGIN_RANGED)
end

-- Inferno arrows and thunder bolts also heal the shooter on every shot.
function zathrothVipAmmoHeal(player)
	player:addHealth(math.floor(player:getMaxHealth() * 0.03))
	player:addMana(math.floor(player:getMaxMana() * 0.03))
end

-- Bonuses of each VIP item while it is worn, keyed by the item's VIP name.
-- `attributes` are CONDITION_ATTRIBUTES parameters (leech and critical
-- values are hundredths of a percent, protections and buffs are percent,
-- buffs count from 100, capacity percent is added as is). `speed`,
-- `regeneration` and `light` add their own conditions. Every condition uses a
-- sub ID per slot, so pieces stack and never replace spells or each other.
local function allSkills(points, extra)
	local attributes = {
		[CONDITION_PARAM_SKILL_FIST] = points,
		[CONDITION_PARAM_SKILL_CLUB] = points,
		[CONDITION_PARAM_SKILL_SWORD] = points,
		[CONDITION_PARAM_SKILL_AXE] = points,
		[CONDITION_PARAM_SKILL_DISTANCE] = points,
		[CONDITION_PARAM_SKILL_SHIELD] = points,
	}
	for param, value in pairs(extra) do
		attributes[param] = (attributes[param] or 0) + value
	end
	return attributes
end

ZATHROTH_VIP_BONUSES = {
	["ZATHROTH VIP helmet"] = {
		attributes = {
			[CONDITION_PARAM_STAT_MAGICPOINTS] = 6,
			[CONDITION_PARAM_STAT_MAXMANAPOINTS] = 800,
			[CONDITION_PARAM_SKILL_MANA_LEECH_AMOUNT] = 800,
			[CONDITION_PARAM_SKILL_CRITICAL_HIT_CHANCE] = 500,
			[CONDITION_PARAM_ABSORB_HOLYPERCENT] = 8,
			[CONDITION_PARAM_ABSORB_DEATHPERCENT] = 8,
		},
		regeneration = { mana = 40 },
		speed = 20,
	},
	["ZATHROTH VIP armor"] = {
		attributes = {
			[CONDITION_PARAM_STAT_MAXHITPOINTS] = 1500,
			[CONDITION_PARAM_ABSORB_PHYSICALPERCENT] = 10,
			[CONDITION_PARAM_ABSORB_FIREPERCENT] = 10,
			[CONDITION_PARAM_ABSORB_ENERGYPERCENT] = 10,
			[CONDITION_PARAM_ABSORB_ICEPERCENT] = 10,
			[CONDITION_PARAM_ABSORB_EARTHPERCENT] = 10,
		},
		regeneration = { health = 60 },
		speed = 20,
	},
	["ZATHROTH VIP legs"] = {
		attributes = {
			[CONDITION_PARAM_STAT_MAXHITPOINTS] = 800,
			[CONDITION_PARAM_STAT_MAXMANAPOINTS] = 500,
			[CONDITION_PARAM_SKILL_SHIELD] = 5,
			[CONDITION_PARAM_ABSORB_PHYSICALPERCENT] = 6,
			[CONDITION_PARAM_ABSORB_EARTHPERCENT] = 8,
			[CONDITION_PARAM_ABSORB_ICEPERCENT] = 8,
		},
		speed = 20,
	},
	["ZATHROTH VIP boots"] = {
		attributes = {
			[CONDITION_PARAM_ABSORB_PHYSICALPERCENT] = 4,
			[CONDITION_PARAM_ABSORB_LIFEDRAINPERCENT] = 15,
			[CONDITION_PARAM_ABSORB_MANADRAINPERCENT] = 15,
			[CONDITION_PARAM_ABSORB_DROWNPERCENT] = 100,
		},
		regeneration = { health = 30, mana = 30 },
		speed = 100,
	},
	["ZATHROTH VIP shield"] = {
		attributes = {
			[CONDITION_PARAM_SKILL_SHIELD] = 10,
			[CONDITION_PARAM_STAT_MAXHITPOINTS] = 500,
			[CONDITION_PARAM_ABSORB_PHYSICALPERCENT] = 12,
			[CONDITION_PARAM_ABSORB_FIREPERCENT] = 6,
			[CONDITION_PARAM_ABSORB_ENERGYPERCENT] = 6,
			[CONDITION_PARAM_ABSORB_ICEPERCENT] = 6,
			[CONDITION_PARAM_ABSORB_EARTHPERCENT] = 6,
		},
		speed = 20,
	},
	["ZATHROTH VIP sword"] = {
		attributes = allSkills(5, {
			[CONDITION_PARAM_SKILL_SWORD] = 10,
			[CONDITION_PARAM_SKILL_CRITICAL_HIT_CHANCE] = 1000,
			[CONDITION_PARAM_SKILL_CRITICAL_HIT_DAMAGE] = 3000,
			[CONDITION_PARAM_SKILL_LIFE_LEECH_AMOUNT] = 1500,
			[CONDITION_PARAM_SKILL_MANA_LEECH_AMOUNT] = 500,
			[CONDITION_PARAM_BUFF_DAMAGEDEALT] = 115,
		}),
		speed = 20,
	},
	["ZATHROTH VIP axe"] = {
		attributes = allSkills(5, {
			[CONDITION_PARAM_SKILL_AXE] = 10,
			[CONDITION_PARAM_SKILL_CRITICAL_HIT_CHANCE] = 1000,
			[CONDITION_PARAM_SKILL_CRITICAL_HIT_DAMAGE] = 3500,
			[CONDITION_PARAM_SKILL_LIFE_LEECH_AMOUNT] = 1500,
			[CONDITION_PARAM_SKILL_MANA_LEECH_AMOUNT] = 500,
			[CONDITION_PARAM_BUFF_DAMAGEDEALT] = 115,
		}),
		speed = 20,
	},
	["ZATHROTH VIP spears"] = {
		attributes = allSkills(5, {
			[CONDITION_PARAM_SKILL_DISTANCE] = 10,
			[CONDITION_PARAM_SKILL_CRITICAL_HIT_CHANCE] = 1000,
			[CONDITION_PARAM_SKILL_CRITICAL_HIT_DAMAGE] = 2500,
			[CONDITION_PARAM_SKILL_LIFE_LEECH_AMOUNT] = 1000,
			[CONDITION_PARAM_BUFF_DAMAGEDEALT] = 110,
		}),
		speed = 20,
	},
	["ZATHROTH VIP bow"] = {
		attributes = allSkills(5, {
			[CONDITION_PARAM_SKILL_DISTANCE] = 10,
			[CONDITION_PARAM_SKILL_CRITICAL_HIT_CHANCE] = 1000,
			[CONDITION_PARAM_SKILL_CRITICAL_HIT_DAMAGE] = 3500,
			[CONDITION_PARAM_SKILL_LIFE_LEECH_AMOUNT] = 1000,
			[CONDITION_PARAM_SKILL_MANA_LEECH_AMOUNT] = 500,
			[CONDITION_PARAM_BUFF_DAMAGEDEALT] = 115,
		}),
		speed = 20,
	},
	["ZATHROTH VIP crossbow"] = {
		attributes = allSkills(5, {
			[CONDITION_PARAM_SKILL_DISTANCE] = 10,
			[CONDITION_PARAM_SKILL_CRITICAL_HIT_CHANCE] = 1000,
			[CONDITION_PARAM_SKILL_CRITICAL_HIT_DAMAGE] = 4000,
			[CONDITION_PARAM_SKILL_LIFE_LEECH_AMOUNT] = 1000,
			[CONDITION_PARAM_SKILL_MANA_LEECH_AMOUNT] = 500,
			[CONDITION_PARAM_BUFF_DAMAGEDEALT] = 120,
		}),
		speed = 20,
	},
	["ZATHROTH VIP wand"] = {
		attributes = allSkills(5, {
			[CONDITION_PARAM_STAT_MAGICPOINTS] = 10,
			[CONDITION_PARAM_STAT_MAXMANAPOINTS] = 1000,
			[CONDITION_PARAM_SKILL_MANA_LEECH_AMOUNT] = 1000,
			[CONDITION_PARAM_SKILL_CRITICAL_HIT_CHANCE] = 1000,
			[CONDITION_PARAM_SKILL_CRITICAL_HIT_DAMAGE] = 3000,
			[CONDITION_PARAM_BUFF_DAMAGEDEALT] = 115,
		}),
		regeneration = { mana = 60 },
		speed = 20,
	},
	["ZATHROTH VIP rod"] = {
		attributes = allSkills(5, {
			[CONDITION_PARAM_STAT_MAGICPOINTS] = 10,
			[CONDITION_PARAM_STAT_MAXMANAPOINTS] = 1000,
			[CONDITION_PARAM_SKILL_MANA_LEECH_AMOUNT] = 1000,
			[CONDITION_PARAM_SKILL_LIFE_LEECH_AMOUNT] = 500,
			[CONDITION_PARAM_SKILL_CRITICAL_HIT_CHANCE] = 1000,
			[CONDITION_PARAM_BUFF_HEALINGDEALT] = 125,
		}),
		regeneration = { mana = 60 },
		speed = 20,
	},
	["ZATHROTH VIP quiver"] = {
		attributes = {
			[CONDITION_PARAM_SKILL_DISTANCE] = 5,
			[CONDITION_PARAM_SKILL_CRITICAL_HIT_CHANCE] = 500,
			[CONDITION_PARAM_STAT_MAXHITPOINTS] = 300,
			[CONDITION_PARAM_ABSORB_PHYSICALPERCENT] = 4,
		},
		speed = 20,
	},
	["ZATHROTH god quiver"] = {
		attributes = allSkills(10, {
			[CONDITION_PARAM_SKILL_DISTANCE] = 20,
			[CONDITION_PARAM_SKILL_CRITICAL_HIT_CHANCE] = 1500,
			[CONDITION_PARAM_STAT_MAXHITPOINTS] = 1000,
			[CONDITION_PARAM_ABSORB_PHYSICALPERCENT] = 8,
		}),
		regeneration = { health = 50, mana = 50 },
		speed = 50,
	},
	["ZATHROTH VIP backpack"] = {
		attributes = {
			[CONDITION_PARAM_STAT_CAPACITYPERCENT] = 50,
			[CONDITION_PARAM_BUFF_HEALINGRECEIVED] = 110,
		},
		regeneration = { health = 20, mana = 20 },
		light = { level = 8, color = 215 },
		speed = 20,
	},
}

local VIP_SUBID = 6153000
local VIP_REGENERATION_TICKS = 2000
local VIP_CONDITION_TYPES = { CONDITION_ATTRIBUTES, CONDITION_HASTE, CONDITION_REGENERATION, CONDITION_LIGHT }

local function addVipCondition(player, conditionType, subId, parameters)
	local condition = Condition(conditionType, CONDITIONID_DEFAULT)
	condition:setParameter(CONDITION_PARAM_TICKS, -1)
	condition:setParameter(CONDITION_PARAM_SUBID, subId)
	for param, value in pairs(parameters) do
		condition:setParameter(param, value)
	end
	player:addCondition(condition)
end

-- VIP item name whose bonuses each player's slot carries, by player ID.
local appliedBonuses = {}

-- Rebuilds the VIP bonuses of every slot whose VIP item changed. Unchanged
-- slots keep their conditions: removing a health or mana bonus even for a
-- moment would cut current health and mana down to the lower maximum.
local function giveBack(player, health, mana)
	local lostHealth = math.min(health, player:getMaxHealth()) - player:getHealth()
	if lostHealth > 0 then
		player:addHealth(lostHealth)
	end
	local lostMana = math.min(mana, player:getMaxMana()) - player:getMana()
	if lostMana > 0 then
		player:addMana(lostMana)
	end
end

-- Logging out removes the VIP conditions before the player is saved, which
-- cuts health and mana to the base maximum. The logout event stores them
-- first; the login event, which runs after the equipment bonuses are back,
-- gives them back.
function zathrothVipRememberVitals(player)
	appliedBonuses[player:getId()] = nil
	local vitals = player:kv():scoped("zathroth-vip")
	vitals:set("health", player:getHealth())
	vitals:set("mana", player:getMana())
end

function zathrothVipRestoreVitals(player)
	local vitals = player:kv():scoped("zathroth-vip")
	local health = vitals:get("health")
	if health then
		giveBack(player, health, vitals:get("mana") or 0)
		vitals:remove("health")
		vitals:remove("mana")
	end
end

function zathrothVipRefresh(player)
	local applied = appliedBonuses[player:getId()] or {}
	appliedBonuses[player:getId()] = applied
	local health, mana = player:getHealth(), player:getMana()

	for slot = CONST_SLOT_FIRST, CONST_SLOT_LAST do
		local subId = VIP_SUBID + slot
		local item = player:getSlotItem(slot)
		local name = item and item:getName()
		local bonus = name and ZATHROTH_VIP_BONUSES[name]
		local wanted = bonus and name or nil
		-- Every bonus has speed, so a missing haste condition means the
		-- bonuses are gone (for example after logging in again).
		local present = player:getCondition(CONDITION_HASTE, CONDITIONID_DEFAULT, subId) ~= nil
		if applied[slot] ~= wanted or (wanted and not present) then
			for _, conditionType in ipairs(VIP_CONDITION_TYPES) do
				player:removeCondition(conditionType, CONDITIONID_DEFAULT, subId)
			end
			applied[slot] = wanted
			if bonus then
				if bonus.attributes then
					addVipCondition(player, CONDITION_ATTRIBUTES, subId, bonus.attributes)
				end
				addVipCondition(player, CONDITION_HASTE, subId, { [CONDITION_PARAM_SPEED] = bonus.speed })
				if bonus.regeneration then
					local regeneration = bonus.regeneration
					addVipCondition(player, CONDITION_REGENERATION, subId, {
						[CONDITION_PARAM_HEALTHGAIN] = regeneration.health or 0,
						[CONDITION_PARAM_HEALTHTICKS] = VIP_REGENERATION_TICKS,
						[CONDITION_PARAM_MANAGAIN] = regeneration.mana or 0,
						[CONDITION_PARAM_MANATICKS] = VIP_REGENERATION_TICKS,
					})
				end
				if bonus.light then
					addVipCondition(player, CONDITION_LIGHT, subId, {
						[CONDITION_PARAM_LIGHT_LEVEL] = bonus.light.level,
						[CONDITION_PARAM_LIGHT_COLOR] = bonus.light.color,
					})
				end
			end
		end
	end

	-- Bonuses are added one slot at a time, and the engine cuts health and
	-- mana to each intermediate maximum, so give back what was cut, up to the
	-- new maximum.
	giveBack(player, health, mana)
end
