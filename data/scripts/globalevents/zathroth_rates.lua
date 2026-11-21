local restoreRates = GlobalEvent("ZathrothRates")

function restoreRates.onStartup()
	zathrothRestoreRates()
	logger.info("[ZathrothRates] attack speed {}x, spawn {}x, loot {}x", Game.getAttackSpeedRate(), Game.getSpawnRate(), ZATHROTH_LOOT_RATE)
	return true
end

restoreRates:register()
