-- Places Zathroth Popcorn on an open floor tile next to every town's temple,
-- leaving the temple tile itself free for arriving players.
local BLOCKING = { TILESTATE_BLOCKSOLID, TILESTATE_BLOCKPATH, TILESTATE_IMMOVABLEBLOCKSOLID, TILESTATE_IMMOVABLEBLOCKPATH, TILESTATE_FLOORCHANGE, TILESTATE_TELEPORT, TILESTATE_MAGICFIELD, TILESTATE_DEPOT, TILESTATE_MAILBOX, TILESTATE_TRASHHOLDER, TILESTATE_BED }

local function isOpen(position)
	local tile = Tile(position)
	if not tile or not tile:getGround() or tile:getHouse() or not tile:hasFlag(TILESTATE_PROTECTIONZONE) or tile:getCreatureCount() > 0 then
		return false
	end
	for _, flag in ipairs(BLOCKING) do
		if tile:hasFlag(flag) then
			return false
		end
	end
	return true
end

local function openNeighbours(position)
	local count = 0
	for dx = -1, 1 do
		for dy = -1, 1 do
			if (dx ~= 0 or dy ~= 0) and isOpen(Position(position.x + dx, position.y + dy, position.z)) then
				count = count + 1
			end
		end
	end
	return count
end

-- Prefer a tile two or more steps from the temple with open space all
-- around, so the merchant blocks neither a doorway nor the temple tile.
-- Small temples fall back to any open tile next to the temple.
local function findSpot(temple)
	for _, rule in ipairs({ { minDistance = 2, minOpen = 7 }, { minDistance = 1, minOpen = 3 } }) do
		local best, bestScore
		for dx = -5, 5 do
			for dy = -5, 5 do
				local distance = math.max(math.abs(dx), math.abs(dy))
				local position = Position(temple.x + dx, temple.y + dy, temple.z)
				if distance >= rule.minDistance and isOpen(position) then
					local open = openNeighbours(position)
					if open >= rule.minOpen then
						local score = (8 - open) * 10 + distance
						if not bestScore or score < bestScore then
							best, bestScore = position, score
						end
					end
				end
			end
		end
		if best then
			return best
		end
	end
	return nil
end

local spawnPopcorn = GlobalEvent("ZathrothPopcornSpawn")

function spawnPopcorn.onStartup()
	local placed, towns = 0, Game.getTowns()
	for _, town in ipairs(towns) do
		local spot = findSpot(town:getTemplePosition())
		if spot and Game.createNpc("Zathroth Popcorn", spot) then
			placed = placed + 1
		else
			logger.warn("[ZathrothPopcornSpawn] No open tile near the {} temple", town:getName())
		end
	end
	logger.info("[ZathrothPopcornSpawn] Zathroth Popcorn is at {} of {} temples", placed, #towns)
	return true
end

spawnPopcorn:register()
