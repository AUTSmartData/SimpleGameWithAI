import math
import random
import logging
import copy

logging.basicConfig(level=logging.INFO)

log = logging.getLogger("TOURNAMENT")

# League Matchup
# Number of rounds, make sure everyone plays someone they
# haven't played before.
def league_games(contestants, max_games=50):
  games = []
  tries = 0
  if len(contestants) <= 1:
    return []

  player_ones = copy.copy(contestants)
  player_twos = copy.copy(contestants)


  while len(games) < max_games:
    random.shuffle(player_ones)
    random.shuffle(player_twos)
    play_games = zip(player_ones, player_twos)
    games.extend(filter(lambda g: g[0] != g[1], play_games))


  return list(games)[:max_games]

if __name__ == "__main__":
  print league_games(range(0, 10))
