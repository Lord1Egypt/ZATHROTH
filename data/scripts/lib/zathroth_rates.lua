-- Server-wide multipliers set by /setatkspeed, /spawn <number>, /lootrate
-- and /exprate.
-- They are saved in the KV store and restored when the server starts
-- (data/scripts/globalevents/zathroth_rates.lua). Loot and experience start at 10x; 1 means normal.
ZATHROTH_LOOT_RATE = 10
ZATHROTH_EXP_RATE = 10
ZATHROTH_MAX_RATE = 1000

ZATHROTH_RATES = {
	attackspeed = {
		key = "attack-speed",
		label = "attack speed",
		apply = function(rate)
			Game.setAttackSpeedRate(rate)
		end,
	},
	spawn = {
		key = "spawn",
		label = "monster spawn rate",
		apply = function(rate)
			Game.setSpawnRate(rate)
		end,
	},
	loot = {
		key = "loot",
		label = "loot rate",
		apply = function(rate)
			ZATHROTH_LOOT_RATE = rate
		end,
	},
	exp = {
		key = "exp",
		label = "experience rate",
		apply = function(rate)
			ZATHROTH_EXP_RATE = rate
		end,
	},
}

local function store()
	return kv.scoped("zathroth-rates")
end

function zathrothRestoreRates()
	for _, rate in pairs(ZATHROTH_RATES) do
		local value = store():get(rate.key)
		if value then
			rate.apply(value)
		end
	end
end

-- Handles "/<command> <multiplier>" for one of ZATHROTH_RATES.
function zathrothRateCommand(player, name, param)
	local rate = ZATHROTH_RATES[name]
	local value = tonumber(param:match("^%s*(%d+)%s*$"))
	if not value or value < 1 or value > ZATHROTH_MAX_RATE then
		player:sendCancelMessage(string.format("Give a whole number from 1 to %d. 1 is normal, 200 is 200x.", ZATHROTH_MAX_RATE))
		return true
	end

	rate.apply(value)
	store():set(rate.key, value)
	local message = string.format("%s set the %s to %dx.", player:getName(), rate.label, value)
	Game.broadcastMessage(message, MESSAGE_GAME_HIGHLIGHT)
	logger.info("[ZathrothRates] {}", message)
	return true
end
