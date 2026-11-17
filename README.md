# gta6-twitch-forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Tianyc1028/gta6-twitch-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Tianyc1028/gta6-twitch-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecasts how many people watch Grand Theft Auto VI live on Twitch in each
hour of its release day, 2026-11-19 (UTC), from the first hour's print:
five quantiles (5%, 25%, 50%, 75%, 95%) of concurrent viewers for each of
hours 2-24.

The model learns at run time from the past big launches shipped in the case
file. It keeps the launches whose unlock rolled round the world at local
midnight, the way GTA VI unlocks, and fits one log-log line per hour:
log(viewers_h / viewers_1) against log(viewers_1). The data shows the
evening rise is steepest when hour 1 is small and nearly flat when hour 1
is already huge, and this fit captures exactly that. The quantile bands
come from each hour's residual scatter, so harder hours get wider bands.
Fully deterministic, standard library only, no network. On the kit's four
practice launches it scores a mean pinball loss of 0.162, against the house
baseline's 0.387.

## Run it

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

The program reads every `*.in` case in the input directory and writes one
`*.out` forecast per case to the output directory. Each output is
`{"hours": [{"hour": 2, "q": [q05, q25, q50, q75, q95]}, ...]}` for hours
2-24.

---

<sub>Entered on [make.fun](https://make.fun/?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
