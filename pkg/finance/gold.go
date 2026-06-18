package finance

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"
)

type SJCGold struct {
	Name string
	Buy  int
	Sell int
}

func GetVietnamGoldPrices() (map[string]SJCGold, error) {
	req, _ := http.NewRequest("GET", "https://www.vang.today/api/prices", nil)
	req.Header.Set("User-Agent", "Mozilla/5.0")
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Do(req)

	if err == nil && resp.StatusCode == 200 {
		var data struct {
			Success bool                   `json:"success"`
			Prices  map[string]interface{} `json:"prices"`
		}
		if err := json.NewDecoder(resp.Body).Decode(&data); err == nil && data.Success {
			var sjcData map[string]interface{}
			keys := []string{"SJL1L10", "BTSJC", "VNGSJC"}
			for _, k := range keys {
				if v, ok := data.Prices[k].(map[string]interface{}); ok {
					sjcData = v
					break
				}
			}

			if sjcData != nil {
				name, _ := sjcData["name"].(string)
				if name == "" {
					name = "SJC 9999"
				}

				var buy, sell int

				switch v := sjcData["buy"].(type) {
				case string:
					buy, _ = strconv.Atoi(v)
				case float64:
					buy = int(v)
				}

				switch v := sjcData["sell"].(type) {
				case string:
					sell, _ = strconv.Atoi(v)
				case float64:
					sell = int(v)
				}

				resp.Body.Close()
				return map[string]SJCGold{
					"sjc": {Name: name, Buy: buy, Sell: sell},
				}, nil
			}
		}
		resp.Body.Close()
	} else if resp != nil {
		resp.Body.Close()
	}

	reqBTMC, _ := http.NewRequest("GET", "http://api.btmc.vn/api/BTMCAPI/getpricebtmc?key=3hP56Sv7%24%25", nil)
	reqBTMC.Header.Set("User-Agent", "Mozilla/5.0")
	respBTMC, err := client.Do(reqBTMC)
	if err != nil {
		return nil, err
	}
	defer respBTMC.Body.Close()

	if respBTMC.StatusCode != 200 {
		return nil, fmt.Errorf("BTMC status: %d", respBTMC.StatusCode)
	}

	var btmcData struct {
		DataList struct {
			Data []map[string]interface{} `json:"Data"`
		} `json:"DataList"`
	}

	if err := json.NewDecoder(respBTMC.Body).Decode(&btmcData); err != nil {
		return nil, err
	}

	for _, item := range btmcData.DataList.Data {
		rowId, ok := item["@row"].(string)
		if !ok || rowId == "" {
			continue
		}
		name, _ := item["@n_"+rowId].(string)
		if strings.Contains(strings.ToUpper(name), "SJC") {
			buyStr, _ := item["@pb_"+rowId].(string)
			sellStr, _ := item["@ps_"+rowId].(string)

			buy, _ := strconv.Atoi(buyStr)
			sell, _ := strconv.Atoi(sellStr)

			return map[string]SJCGold{
				"sjc": {Name: name, Buy: buy * 10, Sell: sell * 10},
			}, nil
		}
	}

	return map[string]SJCGold{}, nil
}

func GetUSGoldPrice() (*float64, error) {
	req, _ := http.NewRequest("GET", "https://query1.finance.yahoo.com/v8/finance/chart/GC=F", nil)
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
				} `json:"meta"`
			} `json:"result"`
		} `json:"chart"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		return nil, err
	}

	if len(data.Chart.Result) > 0 && data.Chart.Result[0].Meta.RegularMarketPrice != nil {
		return data.Chart.Result[0].Meta.RegularMarketPrice, nil
	}

	return nil, fmt.Errorf("could not determine US gold price")
}
