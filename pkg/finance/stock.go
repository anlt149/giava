package finance

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"
)

type StockData struct {
	Ticker        string
	YahooTicker   string
	Price         float64
	PrevClose     float64
	Change        float64
	ChangePercent float64
	Currency      string
}

func GetStockPrice(ticker string) (*StockData, error) {
	ticker = strings.ToUpper(strings.TrimSpace(ticker))
	yahooTicker := ticker
	if !strings.Contains(yahooTicker, ".") {
		yahooTicker = fmt.Sprintf("%s.VN", ticker)
	}

	url := fmt.Sprintf("https://query1.finance.yahoo.com/v8/finance/chart/%s", yahooTicker)
	req, _ := http.NewRequest("GET", url, nil)
	req.Header.Set("User-Agent", "Mozilla/5.0")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("status code: %d", resp.StatusCode)
	}

	var data struct {
		Chart struct {
			Result []struct {
				Meta struct {
					RegularMarketPrice *float64 `json:"regularMarketPrice"`
					ChartPreviousClose *float64 `json:"chartPreviousClose"`
					Currency           string   `json:"currency"`
				} `json:"meta"`
				Indicators struct {
					Quote []struct {
						Close []*float64 `json:"close"`
					} `json:"quote"`
				} `json:"indicators"`
			} `json:"result"`
		} `json:"chart"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		return nil, err
	}

	if len(data.Chart.Result) == 0 {
		return nil, fmt.Errorf("no result")
	}

	meta := data.Chart.Result[0].Meta
	var price, prevClose float64

	if meta.RegularMarketPrice != nil {
		price = *meta.RegularMarketPrice
	} else {
		quotes := data.Chart.Result[0].Indicators.Quote
		if len(quotes) > 0 {
			closes := quotes[0].Close
			for i := len(closes) - 1; i >= 0; i-- {
				if closes[i] != nil {
					price = *closes[i]
					break
				}
			}
		}
		if price == 0 {
			return nil, fmt.Errorf("could not determine price")
		}
	}

	if meta.ChartPreviousClose != nil {
		prevClose = *meta.ChartPreviousClose
	} else {
		prevClose = price
	}

	change := price - prevClose
	changePercent := 0.0
	if prevClose != 0 {
		changePercent = (change / prevClose) * 100
	}

	return &StockData{
		Ticker:        ticker,
		YahooTicker:   yahooTicker,
		Price:         price,
		PrevClose:     prevClose,
		Change:        change,
		ChangePercent: changePercent,
		Currency:      meta.Currency,
	}, nil
}
