-- Characters and houses saved on another map (ZATHROTH first shipped the
-- Canary starter map) point at towns and tiles that do not exist here.
-- The first time this map starts, send every character to the Thais temple.
local WORLD = "otservbr"

local worldMove = GlobalEvent("ZathrothWorldMove")

function worldMove.onStartup()
	local resultId = db.storeQuery("SELECT `value` FROM `server_config` WHERE `config` = 'zathroth_world'")
	local world = resultId and Result.getString(resultId, "value")
	if resultId then
		Result.free(resultId)
	end
	if world == WORLD then
		return true
	end

	local thais = Town("Thais")
	if not thais then
		logger.error("[ZathrothWorldMove] Town 'Thais' is missing from the map; characters were not moved")
		return true
	end

	local moved = db.query(string.format("UPDATE `players` SET `town_id` = %d, `posx` = 0, `posy` = 0, `posz` = 0", thais:getId()))
		and db.query("DELETE FROM `house_lists`")
		and db.query("DELETE FROM `houses`")
		and db.query("INSERT INTO `server_config` (`config`, `value`) VALUES ('zathroth_world', '" .. WORLD .. "') ON CONFLICT (`config`) DO UPDATE SET `value` = excluded.`value`")
	if moved then
		logger.info("[ZathrothWorldMove] All characters now start at the Thais temple on the {} map", WORLD)
	else
		logger.error("[ZathrothWorldMove] Moving characters to Thais failed; it will be retried on the next start")
	end
	return true
end

worldMove:register()
