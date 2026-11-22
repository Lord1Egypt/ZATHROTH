local onlineRecord = GlobalEvent("OnlineRecord")

function onlineRecord.onRecord(current, old)
	-- Load-test bots (tools/loadtest.py) are not real players; do not announce records they cause.
	for _, player in ipairs(Game.getPlayers()) do
		if player:getName():find("^Loadtest ") then
			return true
		end
	end
	addEvent(Game.broadcastMessage, 150, "New record: " .. current .. " players are logged in.", MESSAGE_LOGIN)
	return true
end

onlineRecord:register()
