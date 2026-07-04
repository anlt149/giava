package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/robfig/cron/v3"

	"giava/pkg/finance"
	"giava/pkg/models"
	"giava/pkg/storage"
	"giava/pkg/utils"
)

const stateFile = "gold_price_state.json"

func sendTelegramMessage(botToken string, chatID string, message string) error {
	url := fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", botToken)
	payload := map[string]interface{}{
		"chat_id":    chatID,
		"text":       message,
		"parse_mode": "MarkdownV2",
	}
	data, _ := json.Marshal(payload)
	resp, err := http.Post(url, "application/json", bytes.NewBuffer(data))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		body, _ := io.ReadAll(resp.Body)
		errMsg := string(body)
		
		// Send fallback error message
		fallbackPayload := map[string]interface{}{
			"chat_id": chatID,
			"text":    "⚠️ Lỗi hiển thị báo cáo tự động: " + errMsg,
		}
		fallbackData, _ := json.Marshal(fallbackPayload)
		http.Post(url, "application/json", bytes.NewBuffer(fallbackData))
		
		return fmt.Errorf("status: %d, body: %s", resp.StatusCode, errMsg)
	}
	return nil
}

func checkPrices() {
	botToken := os.Getenv("TELEGRAM_BOT_TOKEN")
	chatID := os.Getenv("TELEGRAM_CHAT_ID")

	if botToken == "" || chatID == "" {
		fmt.Println("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID. Skipping notification.")
	}

	var oldState models.GoldPriceState
	data, err := os.ReadFile(stateFile)
	if err == nil {
		json.Unmarshal(data, &oldState)
	}
	if oldState.StockPrices == nil {
		oldState.StockPrices = make(map[string]float64)
	}

	newState := oldState
	newState.StockPrices = make(map[string]float64)
	for k, v := range oldState.StockPrices {
		newState.StockPrices[k] = v
	}
	newState.LastUpdated = time.Now().UTC().Format(time.RFC3339)

	// 1. Gold
	goldChanged := false
	var goldMsg string
	currentPrices, _ := finance.GetVietnamGoldPrices()
	if sjc, ok := currentPrices["sjc"]; ok {
		currentBuy := sjc.Buy
		currentSell := sjc.Sell

		if currentBuy != oldState.SjcBuy || currentSell != oldState.SjcSell {
			fmt.Printf("Gold price changed! Old: %d/%d -> New: %d/%d\n", oldState.SjcBuy, oldState.SjcSell, currentBuy, currentSell)

			diffBuy := 0
			if oldState.SjcBuy != 0 {
				diffBuy = currentBuy - oldState.SjcBuy
			}
			diffSell := 0
			if oldState.SjcSell != 0 {
				diffSell = currentSell - oldState.SjcSell
			}

			nowStr := time.Now().Format("15:04 02/01/2006")
			goldMsg = "🔔 *BÁO CÁO GIÁ VÀNG*\n\n"
			goldMsg += fmt.Sprintf("🇻🇳 *%s*\n", utils.EscapeMarkdown(sjc.Name))
			
			var buyStr string
			if oldState.SjcBuy != 0 {
				buyStr = fmt.Sprintf("\\- Mua vào: %s \\-\\> %s VND", utils.EscapeMarkdown(utils.FormatCurrency(float64(oldState.SjcBuy))), utils.EscapeMarkdown(utils.FormatCurrency(float64(sjc.Buy))))
			} else {
				buyStr = fmt.Sprintf("\\- Mua vào: %s VND", utils.EscapeMarkdown(utils.FormatCurrency(float64(sjc.Buy))))
			}
			if diffBuy != 0 {
				sign := ""
				if diffBuy > 0 {
					sign = "+"
				}
				buyStr += fmt.Sprintf(" \\(%s%s\\)", utils.EscapeMarkdown(sign), utils.EscapeMarkdown(utils.FormatCurrency(float64(diffBuy))))
			}
			goldMsg += buyStr + "\n"

			var sellStr string
			if oldState.SjcSell != 0 {
				sellStr = fmt.Sprintf("\\- Bán ra: %s \\-\\> %s VND", utils.EscapeMarkdown(utils.FormatCurrency(float64(oldState.SjcSell))), utils.EscapeMarkdown(utils.FormatCurrency(float64(sjc.Sell))))
			} else {
				sellStr = fmt.Sprintf("\\- Bán ra: %s VND", utils.EscapeMarkdown(utils.FormatCurrency(float64(sjc.Sell))))
			}
			if diffSell != 0 {
				sign := ""
				if diffSell > 0 {
					sign = "+"
				}
				sellStr += fmt.Sprintf(" \\(%s%s\\)", utils.EscapeMarkdown(sign), utils.EscapeMarkdown(utils.FormatCurrency(float64(diffSell))))
			}
			goldMsg += sellStr + "\n\n"

			usPrice, _ := finance.GetUSGoldPrice()
			if usPrice != nil {
				goldMsg += fmt.Sprintf("🇺🇸 *Vàng Thế Giới \\(USD/oz\\):* $\\%s\n\n", utils.EscapeMarkdown(utils.FormatCurrency(*usPrice)))
			}
			goldMsg += fmt.Sprintf("Cập nhật lúc: %s", utils.EscapeMarkdown(nowStr))
			
			goldChanged = true
			newState.SjcBuy = currentBuy
			newState.SjcSell = currentSell
		} else {
			fmt.Println("No change in Vietnam gold price.")
		}
	}

	// 2. Stock Check
	type StockChange struct {
		Ticker        string
		Price         float64
		OldPrice      float64
		Change        float64
		ChangePercent float64
	}
	var stockChangedItems []StockChange

	prefs, _ := storage.LoadPrefs()
	if len(prefs.FavoriteStocks) > 0 {
		fmt.Printf("Checking watchlist stocks: %v...\n", prefs.FavoriteStocks)
		for _, ticker := range prefs.FavoriteStocks {
			stockData, _ := finance.GetStockPrice(ticker)
			if stockData != nil {
				currentPrice := stockData.Price
				oldPrice := newState.StockPrices[ticker]

				if currentPrice != oldPrice {
					fmt.Printf("Stock %s price changed! Old: %f -> New: %f\n", ticker, oldPrice, currentPrice)
					stockChangedItems = append(stockChangedItems, StockChange{
						Ticker:        ticker,
						Price:         currentPrice,
						OldPrice:      oldPrice,
						Change:        stockData.Change,
						ChangePercent: stockData.ChangePercent,
					})
					newState.StockPrices[ticker] = currentPrice
				} else {
					fmt.Printf("No change in stock price for %s.\n", ticker)
				}
			}
		}
	}

	var stockMsg string
	if len(stockChangedItems) > 0 {
		nowStr := time.Now().Format("15:04 02/01/2006")
		stockMsg = "🔔 *BÁO CÁO BIẾN ĐỘNG CỔ PHIẾU*\n\n"
		for _, item := range stockChangedItems {
			priceStr := utils.FormatCurrency(item.Price)
			if item.OldPrice > 0 {
				diff := item.Price - item.OldPrice
				sign := ""
				indicator := "⚪"
				if diff > 0 {
					sign = "+"
					indicator = "🟢"
				} else if diff < 0 {
					indicator = "🔴"
				}
				diffPercent := (diff / item.OldPrice) * 100
				diffStr := utils.FormatCurrency(diff)
				if diff == 0 {
					diffStr = priceStr
				}

				stockMsg += fmt.Sprintf("⚫ *%s*\n", utils.EscapeMarkdown(item.Ticker))
				stockMsg += fmt.Sprintf("💰 Giá: %s \\-\\> %s VND\n", utils.EscapeMarkdown(utils.FormatCurrency(item.OldPrice)), utils.EscapeMarkdown(priceStr))
				stockMsg += fmt.Sprintf("📊 Biến động: %s %s%s VND \\(%s%s%%\\)\n\n", indicator, utils.EscapeMarkdown(sign), utils.EscapeMarkdown(diffStr), utils.EscapeMarkdown(sign), utils.EscapeMarkdown(fmt.Sprintf("%.2f", diffPercent)))
			} else {
				stockMsg += fmt.Sprintf("⚫ *%s*\n", utils.EscapeMarkdown(item.Ticker))
				stockMsg += fmt.Sprintf("💰 Giá hiện tại: %s VND \\(Bắt đầu theo dõi\\)\n\n", utils.EscapeMarkdown(priceStr))
			}
		}
		stockMsg += fmt.Sprintf("Cập nhật lúc: %s", utils.EscapeMarkdown(nowStr))
	}

	// 3. Send Notifications
	if goldChanged && goldMsg != "" {
		if botToken != "" && chatID != "" {
			if err := sendTelegramMessage(botToken, chatID, goldMsg); err == nil {
				oldState.SjcBuy = newState.SjcBuy
				oldState.SjcSell = newState.SjcSell
				fmt.Println("Gold notification sent to Telegram.")
			} else {
				fmt.Printf("Failed to send Gold Telegram message: %v\n", err)
			}
		} else {
			oldState.SjcBuy = newState.SjcBuy
			oldState.SjcSell = newState.SjcSell
		}
	}

	if len(stockChangedItems) > 0 && stockMsg != "" {
		if botToken != "" && chatID != "" {
			if err := sendTelegramMessage(botToken, chatID, stockMsg); err == nil {
				oldState.StockPrices = newState.StockPrices
				fmt.Println("Stock notification sent to Telegram.")
			} else {
				fmt.Printf("Failed to send Stock Telegram message: %v\n", err)
			}
		} else {
			oldState.StockPrices = newState.StockPrices
		}
	}

	oldState.LastUpdated = newState.LastUpdated

	stateData, err := json.MarshalIndent(oldState, "", "  ")
	if err == nil {
		os.WriteFile(stateFile, stateData, 0644)
		fmt.Println("State file updated.")
	}
}

func main() {
	schedule := os.Getenv("CRON_SCHEDULE")
	if schedule == "" {
		schedule = "@hourly"
	}

	c := cron.New()
	_, err := c.AddFunc(schedule, func() {
		fmt.Println("Running scheduled checkPrices at", time.Now().Format(time.RFC3339))
		checkPrices()
	})
	if err != nil {
		fmt.Printf("Error adding cron job: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("Starting cron scheduler with schedule: %s\n", schedule)
	
	fmt.Println("Running initial checkPrices at startup...")
	checkPrices()

	c.Start()

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, os.Interrupt, syscall.SIGTERM)
	<-sig
	
	fmt.Println("Shutting down cron scheduler...")
	c.Stop()
}
