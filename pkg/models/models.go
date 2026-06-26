package models

type Asset struct {
	Quantity    float64 `json:"quantity"`
	DCAPrice    float64 `json:"dca_price"`
	RealizedPnL float64 `json:"realized_pnl"`
}

type Portfolio struct {
	Assets map[string]Asset `json:"assets"`
}

type UserPrefs struct {
	FavoriteStocks []string  `json:"favorite_stocks"`
	Portfolio      Portfolio `json:"portfolio"`
}

type TelegramUpdate struct {
	Message       *TelegramMessage       `json:"message"`
	CallbackQuery *TelegramCallbackQuery `json:"callback_query"`
}

type TelegramCallbackQuery struct {
	ID      string           `json:"id"`
	From    *TelegramChat    `json:"from"`
	Message *TelegramMessage `json:"message"`
	Data    string           `json:"data"`
}

type TelegramMessage struct {
	Text string        `json:"text"`
	Chat *TelegramChat `json:"chat"`
}

type TelegramChat struct {
	ID int64 `json:"id"`
}

type GoldPriceState struct {
	SjcBuy      int                `json:"sjc_buy"`
	SjcSell     int                `json:"sjc_sell"`
	StockPrices map[string]float64 `json:"stock_prices"`
	LastUpdated string             `json:"last_updated"`
}
