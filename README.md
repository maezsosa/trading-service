# trading-service

Esqueleto de un sistema de trading automatizado, con capas desacopladas para
que se pueda pasar de backtest a paper trading a trading en vivo sin
reescribir la lógica de estrategia o de riesgo.

## Arquitectura

```
data/       MarketDataProvider: fuente de barras OHLCV (CSV, sintético, o un
            exchange real vía ccxt más adelante). Misma interfaz para
            histórico y tiempo real.

strategy/   Strategy: recibe una barra, opcionalmente devuelve una Signal.
            No sabe nada de tamaño de posición, cuenta ni ejecución.

risk/       RiskManager: único punto de paso entre una Signal y una Order.
            Calcula el tamaño de posición (según distancia al stop),
            aplica límites de exposición por símbolo y totales, un límite
            de pérdida diaria (pausa blanda) y un kill switch de máximo
            drawdown (halt duro hasta reset manual).

broker/     Broker: ejecuta una Order y devuelve un Fill. PaperBroker
            simula fills al precio de mercado y lleva la cuenta (cash,
            posiciones, PnL realizado). Un broker real implementa la misma
            interfaz.

backtest/   Backtester: reproduce barras a través de
            strategy -> risk manager -> broker, usando las mismas clases
            que usaría un run en vivo.

core/       Tipos compartidos: Bar, Signal, Order, Fill, Position,
            AccountState.
```

La idea es que **estrategia y riesgo nunca cambian entre backtest y
producción** — solo cambia qué `MarketDataProvider` y qué `Broker` se
conectan.

## Uso rápido

```bash
pip install -r requirements.txt

# Corre un backtest de ejemplo (datos sintéticos + cruce de medias móviles)
python main.py

# Tests
pytest
```

## Gestión de riesgo (`risk/manager.py`)

Reglas configurables vía `RiskConfig`:

- **Position sizing por volatilidad**: el tamaño de cada operación se
  calcula para que, si se toca el stop, la pérdida sea `risk_per_trade_pct`
  del equity — no un tamaño fijo de contratos/monedas.
- **`max_position_pct`**: tope de exposición a un solo símbolo.
- **`max_total_exposure_pct`**: tope de exposición total del portfolio.
- **`max_daily_loss_pct`**: pausa nuevas operaciones si la pérdida
  realizada del día supera este umbral (se resetea al otro día).
- **`max_drawdown_pct`**: kill switch permanente si el equity cae más de
  este % desde su pico; requiere `reset_halt()` manual para reanudar.

El `Backtester` además cierra posiciones automáticamente si el precio toca
el `stop_loss_price` de la orden.

## Agregar una estrategia nueva

Implementar `Strategy.on_bar(bar) -> Signal | None` (ver
`strategy/moving_average_crossover.py` como referencia) y enchufarla en
`main.py` o en el backtester — no requiere tocar el resto del sistema.

## Próximos pasos

- **Data feed real**: implementar `MarketDataProvider` sobre `ccxt` (cripto)
  u otro SDK de broker, para histórico y para streaming en tiempo real.
- **Broker real**: implementar `Broker` contra la API del exchange/broker
  elegido, arrancando en modo *paper*/testnet antes de mover dinero real.
- **Persistencia y logging**: guardar señales, órdenes y fills (DB o
  archivo) para poder auditar y depurar corridas en vivo.
- **Alertas**: notificar (mail/Telegram/etc.) cuando se activa un stop, el
  kill switch, o hay errores de conexión repetidos.
- **Más estrategias**: el sistema está pensado para tener varias
  estrategias corriendo en paralelo, cada una con su propia asignación de
  riesgo.
