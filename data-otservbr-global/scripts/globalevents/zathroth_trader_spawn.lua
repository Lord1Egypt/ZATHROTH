-- Places a Zathroth Trader on an open tile in the main depot of every city.
-- The tiles were chosen by checking the map for walkable protection-zone
-- floor away from the lockers.
local depots = {
	{ town = "Ab'Dendriel", position = Position(32682, 31687, 7) },
	{ town = "Carlin", position = Position(32335, 31781, 7) },
	{ town = "Kazordoon", position = Position(32660, 31912, 8) },
	{ town = "Thais", position = Position(32348, 32228, 7) },
	{ town = "Venore", position = Position(32922, 32076, 7) },
	{ town = "Ankrahmun", position = Position(33124, 32843, 7) },
	{ town = "Edron", position = Position(33168, 31799, 8) },
	{ town = "Farmine", position = Position(33029, 31452, 11) },
	{ town = "Darashia", position = Position(33215, 32462, 8) },
	{ town = "Liberty Bay", position = Position(32336, 32840, 7) },
	{ town = "Port Hope", position = Position(32623, 32742, 7) },
	{ town = "Svargrond", position = Position(32264, 31141, 7) },
	{ town = "Yalahar", position = Position(32778, 31247, 7) },
	{ town = "Gray Beach", position = Position(33444, 31316, 8) },
	{ town = "Krailos", position = Position(33655, 31661, 8) },
	{ town = "Rathleton", position = Position(33633, 31894, 7) },
	{ town = "Roshamuul", position = Position(33548, 32381, 6) },
	{ town = "Issavi", position = Position(33921, 31478, 7) },
	{ town = "Feyrist", position = Position(33492, 32223, 6) },
	{ town = "Marapur and Silvertides", position = Position(33776, 32841, 7) },
	{ town = "Moonfall", position = Position(33796, 32754, 4) },
}

local spawnTraders = GlobalEvent("ZathrothTraderSpawn")

function spawnTraders.onStartup()
	local placed = 0
	for _, depot in ipairs(depots) do
		if Game.createNpc("Zathroth Trader", depot.position) then
			placed = placed + 1
		else
			local pos = depot.position
			logger.warn("[ZathrothTraderSpawn] Could not place the trader in the {} depot at {}, {}, {}", depot.town, pos.x, pos.y, pos.z)
		end
	end
	logger.info("[ZathrothTraderSpawn] Zathroth Trader is waiting in {} of {} depots", placed, #depots)
	return true
end

spawnTraders:register()
