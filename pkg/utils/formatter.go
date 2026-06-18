package utils

import (
	"golang.org/x/text/language"
	"golang.org/x/text/message"
	"strings"
)

func FormatCurrency(amount float64) string {
	p := message.NewPrinter(language.English)
	s := p.Sprintf("%.0f", amount)
	return strings.ReplaceAll(s, ",", ".")
}

func EscapeMarkdown(text string) string {
	escapeChars := "_*[]()~`>#+-=|{}.!"
	result := ""
	for _, c := range text {
		if strings.ContainsRune(escapeChars, c) {
			result += "\\" + string(c)
		} else {
			result += string(c)
		}
	}
	return result
}
