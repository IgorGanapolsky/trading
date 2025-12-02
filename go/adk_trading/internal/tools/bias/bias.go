package bias

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"time"

	"google.golang.org/adk/tool"
	"google.golang.org/adk/tool/functiontool"
)

type Input struct {
	Symbol string `json:"symbol"`
}

type Output struct {
	Symbol       string    `json:"symbol"`
	Score        float64   `json:"score"`
	Direction    string    `json:"direction"`
	Conviction   float64   `json:"conviction"`
	Reason       string    `json:"reason"`
	Model        string    `json:"model,omitempty"`
	Sources      []string  `json:"sources,omitempty"`
	CreatedAt    time.Time `json:"createdAt"`
	ExpiresAt    time.Time `json:"expiresAt"`
	AgeMinutes   float64   `json:"ageMinutes"`
	Fresh        bool      `json:"fresh"`
	MetadataNote string    `json:"metadataNote,omitempty"`
}

type snapshot struct {
	Symbol     string                 `json:"symbol"`
	Score      float64                `json:"score"`
	Direction  string                 `json:"direction"`
	Conviction float64                `json:"conviction"`
	Reason     string                 `json:"reason"`
	Model      string                 `json:"model"`
	Sources    []string               `json:"sources"`
	CreatedAt  time.Time              `json:"created_at"`
	ExpiresAt  time.Time              `json:"expires_at"`
	Metadata   map[string]interface{} `json:"metadata"`
}

type rawSnapshot struct {
	Symbol     string                 `json:"symbol"`
	Score      float64                `json:"score"`
	Direction  string                 `json:"direction"`
	Conviction float64                `json:"conviction"`
	Reason     string                 `json:"reason"`
	Model      string                 `json:"model"`
	Sources    []string               `json:"sources"`
	CreatedAt  string                 `json:"created_at"`
	ExpiresAt  string                 `json:"expires_at"`
	Metadata   map[string]interface{} `json:"metadata"`
}

// New returns an ADK tool that surfaces bias snapshots published by the slow analyst loop.
func New(biasDir string) (tool.Tool, error) {
	if strings.TrimSpace(biasDir) == "" {
		biasDir = "data/bias"
	}
	handler := func(ctx tool.Context, input Input) Output {
		symbol := strings.ToUpper(strings.TrimSpace(input.Symbol))
		if symbol == "" {
			return Output{}
		}
		latestPath := filepath.Join(biasDir, "latest_biases.json")
		snapshot, err := loadSnapshot(latestPath, symbol)
		if err != nil {
			return Output{Symbol: symbol}
		}
		now := time.Now().UTC()
		ageMinutes := now.Sub(snapshot.CreatedAt).Minutes()
		fresh := now.Before(snapshot.ExpiresAt) && ageMinutes <= 24*60
		metaNote := ""
		if !fresh {
			metaNote = "stale_bias"
		}
		return Output{
			Symbol:       symbol,
			Score:        snapshot.Score,
			Direction:    snapshot.Direction,
			Conviction:   snapshot.Conviction,
			Reason:       snapshot.Reason,
			Model:        snapshot.Model,
			Sources:      snapshot.Sources,
			CreatedAt:    snapshot.CreatedAt,
			ExpiresAt:    snapshot.ExpiresAt,
			AgeMinutes:   ageMinutes,
			Fresh:        fresh,
			MetadataNote: metaNote,
		}
	}

	return functiontool.New(functiontool.Config{
		Name:        "get_bias_snapshot",
		Description: "Load the most recent analyst bias snapshot for a symbol from the shared bias store.",
	}, handler)
}

func loadSnapshot(path string, symbol string) (*snapshot, error) {
	payloads, err := readLatest(path)
	if err != nil {
		return nil, err
	}
	entry, ok := payloads[strings.ToUpper(symbol)]
	if !ok {
		return nil, errors.New("symbol_not_found")
	}
	return entry, nil
}

func readLatest(path string) (map[string]*snapshot, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var blob map[string]rawSnapshot
	if err := json.Unmarshal(data, &blob); err != nil {
		return nil, err
	}
	out := make(map[string]*snapshot, len(blob))
	for sym, snap := range blob {
		sym = strings.ToUpper(sym)
		parsed := snapshot{
			Symbol:     sym,
			Score:      snap.Score,
			Direction:  snap.Direction,
			Conviction: snap.Conviction,
			Reason:     snap.Reason,
			Model:      snap.Model,
			Sources:    append([]string(nil), snap.Sources...),
			CreatedAt:  parseTime(snap.CreatedAt),
			ExpiresAt:  parseTime(snap.ExpiresAt),
			Metadata:   snap.Metadata,
		}
		out[sym] = &parsed
	}
	return out, nil
}

func parseTime(value string) time.Time {
	formats := []string{
		time.RFC3339,
		"2006-01-02T15:04:05",
		"2006-01-02 15:04:05",
	}
	for _, layout := range formats {
		if t, err := time.Parse(layout, value); err == nil {
			return t.UTC()
		}
	}
	return time.Time{}
}
