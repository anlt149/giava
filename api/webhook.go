package api

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"

	"giava/pkg/finance"
	"giava/pkg/models"
	"giava/pkg/storage"
	"giava/pkg/utils"
)

func Handler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusOK)
		return
	}

	body, err := io.ReadAll(r.Body)
	if err != nil || len(body) == 0 {
		w.WriteHeader(http.StatusOK)
		return
	}
	defer r.Body.Close()

	var update models.TelegramUpdate
	if err := json.Unmarshal(body, &update); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		return
	}

	botToken := os.Getenv("TELEGRAM_BOT_TOKEN")
	if update.Message != nil && update.Message.Chat != nil && botToken != "" {
		text := update.Message.Text
		chatID := update.Message.Chat.ID
		fmt.Printf("Received Telegram webhook request. Text: '%s', Chat ID: '%d'\n", text, chatID)

		var msg string
		if strings.HasPrefix(text, "/help") {
			msg = "ℹ️ *DANH SÁCH CÁC CÂU LỆNH HỖ TRỢ*\n\n" +
				"💵 *Thông tin giá thị trường:*\n" +
				"\\- `/gold` : Xem báo cáo giá vàng SJC và Thế Giới\\.\n" +
				"\\- `/stock [TICKER]` : Xem giá cổ phiếu VN \\(ví dụ: `/stock FPT`\\)\\. Mặc định là danh sách theo dõi\\.\n" +
				"\\- `/set_stock <TICKER>` : Thêm cổ phiếu vào danh sách theo dõi\\.\n" +
				"\\- `/remove_stock <TICKER>` : Xoá cổ phiếu khỏi danh sách theo dõi\\.\n\n" +
				"💼 *Quản lý danh mục đầu tư \\(Portfolio\\):*\n" +
				"\\- `/portfolio` hoặc `/assets` : Xem thống kê tài sản, DCA và Lời/Lỗ\\.\n" +
				"\\- `/buy <TICKER/GOLD> <giá> <số lượng>` : Ghi nhận lệnh mua \\(ví dụ: `/buy FPT 120000 100` hoặc `/buy gold 79000000 2`\\)\\.\n" +
				"\\- `/sell <TICKER/GOLD> <giá> <số lượng>` : Ghi nhận lệnh bán \\(ví dụ: `/sell FPT 125000 50` hoặc `/sell gold 80000000 1`\\)\\.\n" +
				"\\- `/clear_portfolio` : Xoá toàn bộ danh mục tài sản\\.\n"
			sendTelegramMessage(botToken, chatID, msg)
		} else if strings.HasPrefix(text, "/gold") {
			msg = buildGoldReportMessage()
			sendTelegramMessage(botToken, chatID, msg)
		} else if strings.HasPrefix(text, "/set_stock") {
			parts := strings.Fields(text)
			if len(parts) < 2 {
				msg = "⚠️ *Vui lòng nhập mã cổ phiếu\\! Ví dụ: `/set_stock FPT`*"
			} else {
				ticker := strings.ToUpper(parts[1])
				stockData, _ := finance.GetStockPrice(ticker)
				if stockData == nil {
					msg = fmt.Sprintf("⚠️ *Không tìm thấy mã cổ phiếu `%s` hoặc lỗi kết nối\\!*", ticker)
				} else {
					success, errStr := addFavoriteStock(ticker)
					if success {
						msg = fmt.Sprintf("✅ *Đã thêm `%s` vào danh sách theo dõi của bạn\\!*", ticker)
					} else {
						msg = fmt.Sprintf("⚠️ *Lỗi:* %s", errStr)
					}
				}
			}
			sendTelegramMessage(botToken, chatID, msg)
		} else if strings.HasPrefix(text, "/remove_stock") {
			parts := strings.Fields(text)
			if len(parts) < 2 {
				msg = "⚠️ *Vui lòng nhập mã cổ phiếu\\! Ví dụ: `/remove_stock FPT`*"
			} else {
				ticker := strings.ToUpper(parts[1])
				success, errStr := removeFavoriteStock(ticker)
				if success {
					msg = fmt.Sprintf("✅ *Đã xoá `%s` khỏi danh sách theo dõi của bạn\\!*", ticker)
				} else {
					msg = fmt.Sprintf("⚠️ *Lỗi:* %s", errStr)
				}
			}
			sendTelegramMessage(botToken, chatID, msg)
		} else if strings.HasPrefix(text, "/stock") {
			parts := strings.Fields(text)
			var ticker string
			if len(parts) >= 2 {
				ticker = strings.ToUpper(parts[1])
			}
			if ticker == "" {
				prefs, _ := storage.LoadPrefs()
				if len(prefs.FavoriteStocks) == 0 {
					msg = "⚠️ *Danh sách theo dõi trống\\! Sử dụng `/set_stock <TICKER>` hoặc `/stock <TICKER>`\\!*"
				} else {
					msg = buildWatchlistReport(prefs.FavoriteStocks)
				}
			} else {
				stockData, _ := finance.GetStockPrice(ticker)
				msg = buildStockReportMessage(stockData)
			}
			sendTelegramMessage(botToken, chatID, msg)
		} else if strings.HasPrefix(text, "/buy") || strings.HasPrefix(text, "/sell") {
			action := "buy"
			if strings.HasPrefix(text, "/sell") {
				action = "sell"
			}
			parts := strings.Fields(text)
			if len(parts) < 4 {
				actionVi := "MUA"
				if action == "sell" {
					actionVi = "BÁN"
				}
				msg = fmt.Sprintf("⚠️ *Cách sử dụng lệnh %s:*\n`/%s <TICKER/GOLD> <giá> <số lượng>`\n\nVí dụ:\n`/%s FPT 120000 100`\n`/%s GOLD 79000000 2`", actionVi, action, action, action)
			} else {
				asset := strings.ToUpper(parts[1])
				priceStr := strings.ReplaceAll(strings.ReplaceAll(parts[2], ",", ""), ".", "")
				price, err := strconv.ParseFloat(priceStr, 64)
				qty, err2 := strconv.ParseFloat(parts[3], 64)
				if err != nil || err2 != nil {
					msg = "⚠️ *Lỗi: Giá và số lượng phải là số\\!*"
				} else {
					if asset != "GOLD" && price < 1000 {
						price = price * 1000
					}
					success, errStr := addTransaction(asset, price, qty, action)
					if success {
						actionVi := "Ghi nhận mua"
						if action == "sell" {
							actionVi = "Ghi nhận bán"
						}
						msg = fmt.Sprintf("✅ *%s thành công\\!*\n🔠 Tài sản: `%s`\n💰 Giá: `%s` VND\n📊 Số lượng: `%s`", actionVi, utils.EscapeMarkdown(asset), utils.EscapeMarkdown(utils.FormatCurrency(price)), utils.EscapeMarkdown(fmt.Sprintf("%g", qty)))
					} else {
						msg = fmt.Sprintf("⚠️ *Lỗi:* %s", errStr)
					}
				}
			}
			sendTelegramMessage(botToken, chatID, msg)
		} else if strings.HasPrefix(text, "/portfolio") || strings.HasPrefix(text, "/assets") {
			msg = getPortfolioReport()
			sendTelegramMessage(botToken, chatID, msg)
		} else if strings.HasPrefix(text, "/clear_portfolio") {
			prefs, _ := storage.LoadPrefs()
			prefs.Portfolio.Assets = make(map[string]models.Asset)
			storage.SavePrefs(prefs)
			msg = "✅ *Đã xoá toàn bộ danh mục tài sản của bạn\\!*"
			sendTelegramMessage(botToken, chatID, msg)
		} else {
			allowedCmds := []string{"/gold", "/set_stock", "/remove_stock", "/stock", "/help", "/buy", "/sell", "/portfolio", "/assets", "/clear_portfolio"}
			found := false
			for _, cmd := range allowedCmds {
				if strings.HasPrefix(text, cmd) {
					found = true
					break
				}
			}
			if !found {
				fmt.Printf("Ignored message: '%s' (unrecognized command)\n", text)
			}
		}
	}

	w.WriteHeader(http.StatusOK)
	w.Write([]byte("OK"))
}

func sendTelegramMessage(botToken string, chatID int64, message string) {
	url := fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", botToken)
	payload := map[string]interface{}{
		"chat_id":    chatID,
		"text":       message,
		"parse_mode": "MarkdownV2",
	}
	data, _ := json.Marshal(payload)
	resp, err := http.Post(url, "application/json", bytes.NewBuffer(data))
	if err == nil {
		if resp.StatusCode != 200 {
			body, _ := io.ReadAll(resp.Body)
			errMsg := string(body)
			fmt.Printf("Telegram API error: %d %s\n", resp.StatusCode, errMsg)
			
			// Send fallback error message to the user
			fallbackPayload := map[string]interface{}{
				"chat_id": chatID,
				"text":    "⚠️ *Lỗi hiển thị tin nhắn:* " + errMsg,
			}
			fallbackData, _ := json.Marshal(fallbackPayload)
			http.Post(url, "application/json", bytes.NewBuffer(fallbackData))
		}
		resp.Body.Close()
	} else {
		fmt.Printf("Telegram POST error: %v\n", err)
	}
}

func buildGoldReportMessage() string {
	vnPrices, _ := finance.GetVietnamGoldPrices()
	usPrice, _ := finance.GetUSGoldPrice()

	sjc, ok := vnPrices["sjc"]
	if !ok {
		return "⚠️ *Không thể lấy được giá vàng SJC lúc này\\. Vui lòng thử lại sau\\!*"
	}

	nowStr := time.Now().Format("15:04 02/01/2006")
	msg := "🔔 *BÁO CÁO GIÁ VÀNG*\n\n"
	msg += fmt.Sprintf("🇻🇳 *%s*\n", utils.EscapeMarkdown(sjc.Name))
	msg += fmt.Sprintf("\\- Mua vào: %s VND\n", utils.EscapeMarkdown(utils.FormatCurrency(float64(sjc.Buy))))
	msg += fmt.Sprintf("\\- Bán ra: %s VND\n\n", utils.EscapeMarkdown(utils.FormatCurrency(float64(sjc.Sell))))

	if usPrice != nil {
		msg += fmt.Sprintf("🇺🇸 *Vàng Thế Giới \\(USD/oz\\):* $\\%s\n\n", utils.EscapeMarkdown(utils.FormatCurrency(*usPrice)))
	}
	msg += fmt.Sprintf("Cập nhật lúc: %s", utils.EscapeMarkdown(nowStr))
	return msg
}

func addFavoriteStock(ticker string) (bool, string) {
	prefs, _ := storage.LoadPrefs()
	for _, f := range prefs.FavoriteStocks {
		if f == ticker {
			return false, fmt.Sprintf("`%s` đã có sẵn trong danh sách theo dõi\\!", ticker)
		}
	}
	prefs.FavoriteStocks = append(prefs.FavoriteStocks, ticker)
	storage.SavePrefs(prefs)
	return true, fmt.Sprintf("Đã thêm `%s` vào danh sách theo dõi\\!", ticker)
}

func removeFavoriteStock(ticker string) (bool, string) {
	prefs, _ := storage.LoadPrefs()
	for i, f := range prefs.FavoriteStocks {
		if f == ticker {
			prefs.FavoriteStocks = append(prefs.FavoriteStocks[:i], prefs.FavoriteStocks[i+1:]...)
			storage.SavePrefs(prefs)
			return true, fmt.Sprintf("Đã xoá `%s` khỏi danh sách theo dõi\\!", ticker)
		}
	}
	return false, fmt.Sprintf("`%s` không có trong danh sách theo dõi\\!", ticker)
}

func buildStockReportMessage(stockData *finance.StockData) string {
	if stockData == nil {
		return "⚠️ *Không thể lấy thông tin cổ phiếu lúc này\\!*"
	}
	nowStr := time.Now().Format("15:04 02/01/2006")
	sign := ""
	indicator := "⚪"
	if stockData.Change > 0 {
		sign = "+"
		indicator = "🟢"
	} else if stockData.Change < 0 {
		indicator = "🔴"
	}

	priceStr := utils.FormatCurrency(stockData.Price)
	changeStr := utils.FormatCurrency(stockData.Change)
	if stockData.Change == 0 {
		changeStr = priceStr
	}

	msg := "📈 *BÁO CÁO CỔ PHIẾU VN*\n\n"
	msg += fmt.Sprintf("🔠 *Mã cổ phiếu:* %s\n", utils.EscapeMarkdown(stockData.Ticker))
	msg += fmt.Sprintf("💰 *Giá hiện tại:* %s VND\n", utils.EscapeMarkdown(priceStr))
	msg += fmt.Sprintf("📊 *Biến động:* %s %s%s VND \\(%s%s%%\\)\n\n", indicator, utils.EscapeMarkdown(sign), utils.EscapeMarkdown(changeStr), utils.EscapeMarkdown(sign), utils.EscapeMarkdown(fmt.Sprintf("%.2f", stockData.ChangePercent)))
	msg += fmt.Sprintf("Cập nhật lúc: %s", utils.EscapeMarkdown(nowStr))
	return msg
}

func buildWatchlistReport(tickers []string) string {
	if len(tickers) == 0 {
		return "📈 *Danh sách theo dõi của bạn đang trống\\!*\nSử dụng `/set_stock <TICKER>` để thêm cổ phiếu\\!"
	}
	sort.Strings(tickers)
	nowStr := time.Now().Format("15:04 02/01/2006")
	msg := "📈 *DANH SÁCH THEO DÕI CỔ PHIẾU*\n\n"

	for _, ticker := range tickers {
		stockData, _ := finance.GetStockPrice(ticker)
		if stockData != nil {
			sign := ""
			indicator := "⚪"
			if stockData.Change > 0 {
				sign = "+"
				indicator = "🟢"
			} else if stockData.Change < 0 {
				indicator = "🔴"
			}
			priceStr := utils.FormatCurrency(stockData.Price)
			changeStr := utils.FormatCurrency(stockData.Change)
			if stockData.Change == 0 {
				changeStr = priceStr
			}

			msg += fmt.Sprintf("⚫ *%s*\n", utils.EscapeMarkdown(ticker))
			msg += fmt.Sprintf("💰 Giá: %s VND\n", utils.EscapeMarkdown(priceStr))
			msg += fmt.Sprintf("📊 Biến động: %s %s%s VND \\(%s%s%%\\)\n\n", indicator, utils.EscapeMarkdown(sign), utils.EscapeMarkdown(changeStr), utils.EscapeMarkdown(sign), utils.EscapeMarkdown(fmt.Sprintf("%.2f", stockData.ChangePercent)))
		} else {
			msg += fmt.Sprintf("⚫ *%s*\n⚠️ Không thể lấy thông tin giá lúc này\\!\n\n", utils.EscapeMarkdown(ticker))
		}
	}
	msg += fmt.Sprintf("Cập nhật lúc: %s", utils.EscapeMarkdown(nowStr))
	return msg
}

func addTransaction(assetName string, price, quantity float64, action string) (bool, string) {
	if quantity <= 0 {
		return false, "Số lượng phải lớn hơn 0\\!"
	}
	if price <= 0 {
		return false, "Giá phải lớn hơn 0\\!"
	}

	prefs, _ := storage.LoadPrefs()
	assetData, ok := prefs.Portfolio.Assets[assetName]
	if !ok {
		assetData = models.Asset{}
	}

	oldQty := assetData.Quantity
	oldDCA := assetData.DCAPrice
	realizedPnL := assetData.RealizedPnL

	if action == "buy" {
		newQty := oldQty + quantity
		newDCA := 0.0
		if newQty > 0 {
			newDCA = ((oldQty * oldDCA) + (price * quantity)) / newQty
		}
		assetData.Quantity = newQty
		assetData.DCAPrice = newDCA
	} else if action == "sell" {
		if quantity > oldQty {
			return false, fmt.Sprintf("Không đủ số lượng để bán\\! Bạn chỉ có `%s`\\.", utils.EscapeMarkdown(fmt.Sprintf("%g", oldQty)))
		}
		newQty := oldQty - quantity
		realizedPnL += (price - oldDCA) * quantity
		assetData.Quantity = newQty
		assetData.RealizedPnL = realizedPnL
	} else {
		return false, "Hành động không hợp lệ\\!"
	}

	prefs.Portfolio.Assets[assetName] = assetData
	storage.SavePrefs(prefs)
	return true, ""
}

func getPortfolioReport() string {
	prefs, _ := storage.LoadPrefs()
	assets := prefs.Portfolio.Assets
	if len(assets) == 0 {
		return "💼 *Danh mục đầu tư của bạn đang trống\\!*\nSử dụng `/buy` để thêm tài sản\\! Ví dụ: `/buy FPT 120000 100`"
	}

	activeCount := 0
	realizedPnLTotal := 0.0
	for _, v := range assets {
		if v.Quantity > 0 {
			activeCount++
		}
		realizedPnLTotal += v.RealizedPnL
	}

	if activeCount == 0 && realizedPnLTotal == 0.0 {
		return "💼 *Danh mục đầu tư của bạn đang trống\\!*\nSử dụng `/buy` để thêm tài sản\\! Ví dụ: `/buy FPT 120000 100`"
	}

	msg := "💼 *DANH MỤC TÀI SẢN*\n\n"
	totalCost := 0.0
	totalValue := 0.0

	var goldPrices map[string]finance.SJCGold

	// Sort keys
	var keys []string
	for k := range assets {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	for _, assetName := range keys {
		data := assets[assetName]
		if data.Quantity <= 0 {
			continue
		}

		currentPrice := 0.0
		priceFound := false
		if assetName == "GOLD" {
			if goldPrices == nil {
				goldPrices, _ = finance.GetVietnamGoldPrices()
			}
			if sjc, ok := goldPrices["sjc"]; ok {
				currentPrice = float64(sjc.Buy)
				priceFound = true
			}
		} else {
			stockData, _ := finance.GetStockPrice(assetName)
			if stockData != nil {
				currentPrice = stockData.Price
				priceFound = true
			}
		}

		unit := "CP"
		if assetName == "GOLD" {
			unit = "chỉ"
		}

		costBasis := data.Quantity * data.DCAPrice
		totalCost += costBasis

		msg += fmt.Sprintf("⚫ *%s*\n", utils.EscapeMarkdown(assetName))
		msg += fmt.Sprintf("\\- Số lượng: %s %s\n", utils.EscapeMarkdown(fmt.Sprintf("%g", data.Quantity)), unit)
		msg += fmt.Sprintf("\\- Giá DCA: %s VND\n", utils.EscapeMarkdown(utils.FormatCurrency(data.DCAPrice)))

		if priceFound {
			currentVal := data.Quantity * currentPrice
			totalValue += currentVal
			unrealizedPnL := currentVal - costBasis
			pnlPercent := 0.0
			if costBasis > 0 {
				pnlPercent = (unrealizedPnL / costBasis) * 100
			}

			pnlSign := ""
			indicator := "⚪"
			if unrealizedPnL > 0 {
				pnlSign = "+"
				indicator = "🟢"
			} else if unrealizedPnL < 0 {
				indicator = "🔴"
			}

			msg += fmt.Sprintf("\\- Giá hiện tại: %s VND\n", utils.EscapeMarkdown(utils.FormatCurrency(currentPrice)))
			msg += fmt.Sprintf("\\- Giá trị hiện tại: %s VND\n", utils.EscapeMarkdown(utils.FormatCurrency(currentVal)))
			msg += fmt.Sprintf("\\- Lợi nhuận: %s %s%s VND \\(%s%s%%\\)\n", indicator, utils.EscapeMarkdown(pnlSign), utils.EscapeMarkdown(utils.FormatCurrency(unrealizedPnL)), utils.EscapeMarkdown(pnlSign), utils.EscapeMarkdown(fmt.Sprintf("%.2f", pnlPercent)))
		} else {
			totalValue += costBasis
			msg += "⚠️ *Không thể lấy giá hiện tại\\!*\n"
			msg += fmt.Sprintf("\\- Giá trị đầu tư: %s VND\n", utils.EscapeMarkdown(utils.FormatCurrency(costBasis)))
		}
		msg += "\n"
	}

	msg += "───────────────────\n"
	msg += "📊 *TỔNG KẾT TÀI SẢN*\n"
	msg += fmt.Sprintf("\\- Tổng vốn đầu tư: %s VND\n", utils.EscapeMarkdown(utils.FormatCurrency(totalCost)))
	msg += fmt.Sprintf("\\- Tổng giá trị hiện tại: %s VND\n", utils.EscapeMarkdown(utils.FormatCurrency(totalValue)))

	totalUnrealizedPnL := totalValue - totalCost
	totalPnLPercent := 0.0
	if totalCost > 0 {
		totalPnLPercent = (totalUnrealizedPnL / totalCost) * 100
	}

	totalPnLSign := ""
	totalIndicator := "⚪"
	if totalUnrealizedPnL > 0 {
		totalPnLSign = "+"
		totalIndicator = "🟢"
	} else if totalUnrealizedPnL < 0 {
		totalIndicator = "🔴"
	}

	msg += fmt.Sprintf("\\- Lợi nhuận chưa chốt: %s %s%s VND \\(%s%s%%\\)\n", totalIndicator, utils.EscapeMarkdown(totalPnLSign), utils.EscapeMarkdown(utils.FormatCurrency(totalUnrealizedPnL)), utils.EscapeMarkdown(totalPnLSign), utils.EscapeMarkdown(fmt.Sprintf("%.2f", totalPnLPercent)))

	realizedSign := ""
	if realizedPnLTotal > 0 {
		realizedSign = "+"
	} else if realizedPnLTotal < 0 {
		realizedSign = "-"
	}
	realizedIndicator := "⚪"
	if realizedPnLTotal > 0 {
		realizedIndicator = "🟢"
	} else if realizedPnLTotal < 0 {
		realizedIndicator = "🔴"
	}

	absRealized := realizedPnLTotal
	if absRealized < 0 {
		absRealized = -absRealized
	}

	msg += fmt.Sprintf("\\- Lợi nhuận đã chốt: %s %s%s VND\n", realizedIndicator, utils.EscapeMarkdown(realizedSign), utils.EscapeMarkdown(utils.FormatCurrency(absRealized)))
	return msg
}
