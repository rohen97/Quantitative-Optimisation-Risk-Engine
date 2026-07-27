$ErrorActionPreference = "Stop"
schtasks /Delete /TN "WolfQuantDailyProduction" /F
schtasks /Delete /TN "WolfQuantWeeklyProduction" /F
schtasks /Delete /TN "WolfQuantMonthlyProduction" /F
