local restoreRates = GlobalEvent("ZathrothRates")

function restoreRates.onStartup()
	zathrothRestoreRates()
	logger.info("[ZathrothRates] attack speed {}x, spawn {}x, loot {}x, experience {}x", Game.getAttackSpeedRate(), Game.getSpawnRate(), ZATHROTH_LOOT_RATE, ZATHROTH_EXP_RATE)
	return true
end

restoreRates:register()
