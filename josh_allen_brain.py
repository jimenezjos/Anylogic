import random
import nflreadpy as nfl
import polars as pl

pbp_raw = nfl.load_pbp(seasons=[2023])
PBP_PARTIDO = pbp_raw.filter(
    (pl.col("season_type") == "REG") &
    (pl.col("play_type").is_in(["pass", "run"])) &
    (pl.col("down").is_not_null()) &
    ((pl.col("posteam").is_in(["BUF", "KC"])) | (pl.col("defteam").is_in(["BUF", "KC"])))
).select([
    "posteam", "defteam", "down", "ydstogo", "qtr",
    "score_differential", "play_type", "yards_gained",
    "interception", "fumble_lost"
])

def _filtrar_distancia(df: pl.DataFrame, ydstogo: int) -> pl.DataFrame:
    if ydstogo <= 3:
        sub = df.filter(pl.col("ydstogo") <= 3)
    elif ydstogo <= 7:
        sub = df.filter((pl.col("ydstogo") >= 4) & (pl.col("ydstogo") <= 7))
    else:
        sub = df.filter(pl.col("ydstogo") >= 8)
    return sub if not sub.is_empty() else df

def simular_enfrentamiento(ofensiva: str, defensiva: str, down: int, ydstogo: int, va_perdiendo: bool) -> str:
    # 1. Decisión de pase o carrera según equipo, down y yardas por avanzar
    sub_of = PBP_PARTIDO.filter((pl.col("posteam") == ofensiva) & (pl.col("down") == down))
    if sub_of.is_empty():
        sub_of = PBP_PARTIDO.filter(pl.col("posteam") == ofensiva)

    if va_perdiendo:
        sub_q4 = sub_of.filter((pl.col("qtr") == 4) & (pl.col("score_differential") < 0))
        if not sub_q4.is_empty():
            sub_of = sub_q4

    sub_of = _filtrar_distancia(sub_of, ydstogo)
    tipo_jugada = sub_of.sample(n=1, shuffle=True).to_dicts()[0]["play_type"]

    # 2. Resultado: 50% historial ofensivo vs. 50% historial defensivo rival
    if random.random() < 0.5:
        pool = PBP_PARTIDO.filter(
            (pl.col("posteam") == ofensiva) &
            (pl.col("down") == down) &
            (pl.col("play_type") == tipo_jugada)
        )
    else:
        pool = PBP_PARTIDO.filter(
            (pl.col("defteam") == defensiva) &
            (pl.col("down") == down) &
            (pl.col("play_type") == tipo_jugada)
        )

    pool = _filtrar_distancia(pool, ydstogo) if not pool.is_empty() else sub_of

    res = pool.sample(n=1, shuffle=True).to_dicts()[0]
    decision = "LANZAR" if tipo_jugada == "pass" else "CORRER"
    yardas = int(res["yards_gained"] or 0)
    turnover = 1 if (res["interception"] == 1 or res["fumble_lost"] == 1) else 0

    # 3. Consumo de reloj en segundos
    if tipo_jugada == "pass" and yardas == 0 and turnover == 0:
        segundos = random.randint(5, 8)
    else:
        segundos = random.randint(24, 36) if not va_perdiendo else random.randint(15, 25)

    return f"{decision}|{yardas}|{turnover}|{segundos}"