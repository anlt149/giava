package storage

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"

	"giava/pkg/models"
)

const prefsFile = "user_prefs.json"

var PrefsCache *models.UserPrefs

func InitPrefs(prefs *models.UserPrefs) {
	if prefs.Portfolio.Assets == nil {
		prefs.Portfolio.Assets = make(map[string]models.Asset)
	}
}

func LoadPrefs() (*models.UserPrefs, error) {
	if PrefsCache != nil {
		return PrefsCache, nil
	}

	githubToken := os.Getenv("GITHUB_TOKEN")
	owner := os.Getenv("VERCEL_GIT_REPO_OWNER")
	if owner == "" {
		owner = "anlt149"
	}
	repo := os.Getenv("VERCEL_GIT_REPO_SLUG")
	if repo == "" {
		repo = "giava"
	}

	if githubToken != "" {
		url := fmt.Sprintf("https://api.github.com/repos/%s/%s/contents/%s", owner, repo, prefsFile)
		req, _ := http.NewRequest("GET", url, nil)
		req.Header.Set("Authorization", "Bearer "+githubToken)
		req.Header.Set("Accept", "application/vnd.github+json")
		req.Header.Set("X-GitHub-Api-Version", "2022-11-28")
		req.Header.Set("User-Agent", "Telegram-Stock-Bot")

		client := &http.Client{Timeout: 5 * time.Second}
		resp, err := client.Do(req)
		if err == nil {
			if resp.StatusCode == 200 {
				var result struct {
					Content string `json:"content"`
				}
				if err := json.NewDecoder(resp.Body).Decode(&result); err == nil {
					contentBytes, err := base64.StdEncoding.DecodeString(result.Content)
					if err == nil {
						var prefs models.UserPrefs
						if err := json.Unmarshal(contentBytes, &prefs); err == nil {
							InitPrefs(&prefs)
							PrefsCache = &prefs
							resp.Body.Close()
							return PrefsCache, nil
						}
					}
				}
			}
			resp.Body.Close()
		}
	}

	if _, err := os.Stat(prefsFile); err == nil {
		data, err := os.ReadFile(prefsFile)
		if err == nil {
			var prefs models.UserPrefs
			if err := json.Unmarshal(data, &prefs); err == nil {
				InitPrefs(&prefs)
				PrefsCache = &prefs
				return PrefsCache, nil
			}
		}
	}

	prefs := &models.UserPrefs{}
	InitPrefs(prefs)
	return prefs, nil
}

func SavePrefs(prefs *models.UserPrefs) error {
	PrefsCache = prefs

	data, err := json.MarshalIndent(prefs, "", "  ")
	if err == nil {
		os.WriteFile(prefsFile, data, 0644)
	}

	githubToken := os.Getenv("GITHUB_TOKEN")
	if githubToken == "" {
		return nil
	}

	owner := os.Getenv("VERCEL_GIT_REPO_OWNER")
	if owner == "" {
		owner = "anlt149"
	}
	repo := os.Getenv("VERCEL_GIT_REPO_SLUG")
	if repo == "" {
		repo = "giava"
	}

	url := fmt.Sprintf("https://api.github.com/repos/%s/%s/contents/%s", owner, repo, prefsFile)

	var sha string
	reqGet, _ := http.NewRequest("GET", url, nil)
	reqGet.Header.Set("Authorization", "Bearer "+githubToken)
	reqGet.Header.Set("Accept", "application/vnd.github+json")
	reqGet.Header.Set("X-GitHub-Api-Version", "2022-11-28")
	reqGet.Header.Set("User-Agent", "Telegram-Stock-Bot")

	client := &http.Client{Timeout: 10 * time.Second}
	respGet, err := client.Do(reqGet)
	if err == nil {
		if respGet.StatusCode == 200 {
			var res struct {
				Sha string `json:"sha"`
			}
			json.NewDecoder(respGet.Body).Decode(&res)
			sha = res.Sha
		}
		respGet.Body.Close()
	}

	contentB64 := base64.StdEncoding.EncodeToString(data)
	payload := map[string]interface{}{
		"message": "chore: update user stock preferences via bot",
		"content": contentB64,
	}
	if sha != "" {
		payload["sha"] = sha
	}

	payloadBytes, _ := json.Marshal(payload)
	reqPut, _ := http.NewRequest("PUT", url, bytes.NewBuffer(payloadBytes))
	reqPut.Header.Set("Authorization", "Bearer "+githubToken)
	reqPut.Header.Set("Accept", "application/vnd.github+json")
	reqPut.Header.Set("X-GitHub-Api-Version", "2022-11-28")
	reqPut.Header.Set("User-Agent", "Telegram-Stock-Bot")

	respPut, err := client.Do(reqPut)
	if err != nil {
		return err
	}
	defer respPut.Body.Close()

	if respPut.StatusCode != 200 && respPut.StatusCode != 201 {
		body, _ := io.ReadAll(respPut.Body)
		return fmt.Errorf("failed to update github: %d %s", respPut.StatusCode, string(body))
	}

	return nil
}
