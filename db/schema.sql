PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS games (
    game_id TEXT PRIMARY KEY,
    creator_player_id TEXT,
    start_time DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS game_settings (
    game_id TEXT PRIMARY KEY,
    max_players INTEGER NOT NULL,
    board_size INTEGER NOT NULL,
    board_shrink INTEGER NOT NULL,
    turn_interval INTEGER NOT NULL,
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS game_state (
    game_id TEXT PRIMARY KEY,
    turn_number INTEGER NOT NULL,
    last_turn_time DATETIME,
    next_turn_time DATETIME,
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS players (
    player_id TEXT PRIMARY KEY,
    date_created DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS game_players (
    game_id TEXT,
    player_id TEXT,
    name TEXT NOT NULL,
    color TEXT,
    submitted_turn INTEGER DEFAULT 0,
    PRIMARY KEY (game_id, player_id),
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pieces (
    piece_id TEXT,
    game_id TEXT NOT NULL,
    owner_player_id TEXT,
    x REAL NOT NULL,
    y REAL NOT NULL,
    vx REAL NOT NULL,
    vy REAL NOT NULL,
    radius REAL NOT NULL,
    mass REAL NOT NULL,
    PRIMARY KEY (piece_id, game_id),
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE,
    FOREIGN KEY (owner_player_id) REFERENCES players(player_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS pieces_old (
    piece_id TEXT,
    game_id TEXT NOT NULL,
    owner_player_id TEXT,
    x REAL NOT NULL,
    y REAL NOT NULL,
    vx REAL NOT NULL,
    vy REAL NOT NULL,
    radius REAL NOT NULL,
    mass REAL NOT NULL,
    PRIMARY KEY (piece_id, game_id),
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE,
    FOREIGN KEY (owner_player_id) REFERENCES players(player_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS game_passwords (
    game_id TEXT PRIMARY KEY,
    salt BLOB NOT NULL,
    hashed BLOB NOT NULL,
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS player_passwords (
    player_id TEXT PRIMARY KEY,
    salt BLOB NOT NULL,
    hashed BLOB NOT NULL,
    FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS session_tokens (
    session_token TEXT PRIMARY KEY,
    game_id TEXT,
    player_id TEXT,
    expires_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_game_players_game ON game_players(game_id);
CREATE INDEX IF NOT EXISTS idx_pieces_game ON pieces(game_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON session_tokens(expires_at);

-- Pool of suggested, unused game ids. Applications should `SELECT` and
-- optionally set `leased_until` as a short reservation when recommending
-- a name to a client; the lease prevents immediate re-recommendation.
CREATE TABLE IF NOT EXISTS unused_game_ids (
    name TEXT PRIMARY KEY,
    leased_until DATETIME,
    last_refreshed DATETIME --the time this id was last confirmed as unused
);

-- Prevent inserting a suggested id that already exists as a real game id.
CREATE TRIGGER IF NOT EXISTS unused_game_ids_before_insert
BEFORE INSERT ON unused_game_ids
BEGIN
    SELECT RAISE(ABORT, 'name already used by existing game')
    WHERE EXISTS (SELECT 1 FROM games WHERE game_id = NEW.name);
END;

-- When a game is created with a particular `game_id`, remove any matching
-- suggested id from the pool so the invariant is maintained.
CREATE TRIGGER IF NOT EXISTS games_after_insert_remove_unused_id
AFTER INSERT ON games
WHEN NEW.game_id IS NOT NULL
BEGIN
    DELETE FROM unused_game_ids WHERE name = NEW.game_id;
END;

-- Defensive: if a game's id is ever updated, remove any matching suggested id. (not that this should ever happen)
CREATE TRIGGER IF NOT EXISTS games_after_update_remove_unused_id
AFTER UPDATE ON games
WHEN NEW.game_id IS NOT NULL AND (OLD.game_id IS NULL OR NEW.game_id != OLD.game_id)
BEGIN
    DELETE FROM unused_game_ids WHERE name = NEW.game_id;
END;

-- When a player is added to a game without a creator, make them the creator
CREATE TRIGGER IF NOT EXISTS game_players_after_insert_set_creator
AFTER INSERT ON game_players
WHEN (SELECT creator_player_id FROM games WHERE game_id = NEW.game_id) IS NULL
BEGIN
    UPDATE games SET creator_player_id = NEW.player_id WHERE game_id = NEW.game_id;
END;

-- When a player is deleted, if they were the creator and other players remain, reassign creator to an arbitrary remaining player
CREATE TRIGGER IF NOT EXISTS game_players_after_delete_reassign_creator
AFTER DELETE ON game_players
WHEN (SELECT creator_player_id FROM games WHERE game_id = OLD.game_id) = OLD.player_id
  AND EXISTS (SELECT 1 FROM game_players WHERE game_id = OLD.game_id)
BEGIN
    UPDATE games SET creator_player_id = (
        SELECT player_id FROM game_players WHERE game_id = OLD.game_id LIMIT 1
    ) WHERE game_id = OLD.game_id;
END;

-- When the last player is deleted from a game, clear the creator
CREATE TRIGGER IF NOT EXISTS game_players_after_delete_clear_creator
AFTER DELETE ON game_players
WHEN (SELECT creator_player_id FROM games WHERE game_id = OLD.game_id) = OLD.player_id
  AND NOT EXISTS (SELECT 1 FROM game_players WHERE game_id = OLD.game_id)
BEGIN
    UPDATE games SET creator_player_id = NULL WHERE game_id = OLD.game_id;
END;
