package agents

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/igorganapolsky/trading/adk_trading/internal/observability"
	"github.com/igorganapolsky/trading/adk_trading/internal/tools/bias"
	"github.com/igorganapolsky/trading/adk_trading/internal/tools/logging"
	"github.com/igorganapolsky/trading/adk_trading/internal/tools/marketdata"
	"github.com/igorganapolsky/trading/adk_trading/internal/tools/risk"
	"google.golang.org/adk/agent"
	"google.golang.org/adk/agent/llmagent"
	"google.golang.org/adk/model"
	"google.golang.org/adk/model/gemini"
	"google.golang.org/adk/tool"
	"google.golang.org/adk/tool/agenttool"
	"google.golang.org/genai"
)

type Config struct {
	AppName               string
	ModelName             string
	DataDir               string
	LogPath               string
	PortfolioValue        float64
	ObservabilityRecorder *observability.Recorder
}

func (c Config) validate() error {
	if strings.TrimSpace(c.AppName) == "" {
		return errors.New("app name is required")
	}
	if strings.TrimSpace(c.ModelName) == "" {
		return errors.New("model name is required")
	}
	if strings.TrimSpace(c.DataDir) == "" {
		return errors.New("data directory is required")
	}
	if _, err := os.Stat(c.DataDir); err != nil {
		return fmt.Errorf("data directory not available: %w", err)
	}
	if strings.TrimSpace(c.LogPath) == "" {
		return errors.New("log path is required")
	}
	return nil
}

func BuildTradingOrchestrator(ctx context.Context, cfg Config) (agent.Agent, []agent.Agent, error) {
	if err := cfg.validate(); err != nil {
		return nil, nil, err
	}
	if cfg.PortfolioValue <= 0 {
		cfg.PortfolioValue = 1_000_000
	}

	apiKey := strings.TrimSpace(os.Getenv("GOOGLE_API_KEY"))
	if apiKey == "" {
		return nil, nil, errors.New("GOOGLE_API_KEY environment variable is required for ADK agents")
	}

	geminiModel, err := gemini.NewModel(ctx, cfg.ModelName, &genai.ClientConfig{
		APIKey: apiKey,
	})
	if err != nil {
		return nil, nil, fmt.Errorf("create gemini model: %w", err)
	}

	marketTool, err := marketdata.New(cfg.DataDir)
	if err != nil {
		return nil, nil, fmt.Errorf("market data tool: %w", err)
	}

	biasDir := os.Getenv("BIAS_DATA_DIR")
	if strings.TrimSpace(biasDir) == "" {
		biasDir = filepath.Join(cfg.DataDir, "bias")
	}
	biasTool, err := bias.New(biasDir)
	if err != nil {
		return nil, nil, fmt.Errorf("bias tool: %w", err)
	}

	logTool, err := logging.New(cfg.LogPath, cfg.ObservabilityRecorder)
	if err != nil {
		return nil, nil, fmt.Errorf("logging tool: %w", err)
	}

	riskTool, err := risk.New(cfg.PortfolioValue)
	if err != nil {
		return nil, nil, fmt.Errorf("risk tool: %w", err)
	}

	researchAgent, err := newResearchAgent(geminiModel, marketTool, biasTool)
	if err != nil {
		return nil, nil, err
	}

	signalAgent, err := newSignalAgent(geminiModel, marketTool, biasTool)
	if err != nil {
		return nil, nil, err
	}

	riskAgent, err := newRiskAgent(geminiModel, riskTool)
	if err != nil {
		return nil, nil, err
	}

	executionAgent, err := newExecutionAgent(geminiModel, logTool)
	if err != nil {
		return nil, nil, err
	}

	rootAgent, err := newRootAgent(cfg, geminiModel, researchAgent, signalAgent, riskAgent, executionAgent)
	if err != nil {
		return nil, nil, err
	}

	return rootAgent, []agent.Agent{researchAgent, signalAgent, riskAgent, executionAgent}, nil
}

func newResearchAgent(llm model.LLM, market tool.Tool, bias tool.Tool) (agent.Agent, error) {
	tools := []tool.Tool{market}
	if bias != nil {
		tools = append(tools, bias)
	}
	return llmagent.New(llmagent.Config{
		Name:        "research_agent",
		Model:       llm,
		Description: "Specialist that contextualizes fundamentals, market microstructure and sentiment for a symbol.",
		Instruction: strings.TrimSpace(`
You synthesize recent market structure for the target symbol.
Always call the get_market_snapshot tool before drafting conclusions to inspect quantitative features.
If get_bias_snapshot is available, compare its score with your findings.
Return a concise JSON object with keys:
  - symbol
  - market_regime (bullish, bearish, range-bound)
  - narrative (two sentences max)
  - supporting_metrics (map of indicator -> value)
`),
		Tools: tools,
	})
}

func newSignalAgent(llm model.LLM, market tool.Tool, bias tool.Tool) (agent.Agent, error) {
	tools := []tool.Tool{market}
	if bias != nil {
		tools = append(tools, bias)
	}
	return llmagent.New(llmagent.Config{
		Name:        "signal_agent",
		Model:       llm,
		Description: "Generates directional trade hypotheses with entry/exit targets.",
		Instruction: strings.TrimSpace(`
Leverage research_agent findings and get_market_snapshot as needed to produce a trading signal.
If get_bias_snapshot is available, explicitly state whether you are aligned or deliberately fading it.
Provide JSON with fields:
  - action (BUY, SELL, HOLD)
  - conviction (0-1)
  - entry_window (price range)
  - exit_plan (targets and stop)
`),
		Tools: tools,
	})
}

func newRiskAgent(llm model.LLM, riskTool tool.Tool) (agent.Agent, error) {
	return llmagent.New(llmagent.Config{
		Name:        "risk_agent",
		Model:       llm,
		Description: "Applies portfolio risk guardrails and position sizing heuristics.",
		Instruction: strings.TrimSpace(`
Use the risk_budget_check tool to validate the signal.
If the risk decision is not APPROVE, justify what should change.
Respond in JSON:
  - decision (APPROVE, REVIEW, REJECT)
  - position_size
  - rationale
`),
		Tools: []tool.Tool{riskTool},
	})
}

func newExecutionAgent(llm model.LLM, logTool tool.Tool) (agent.Agent, error) {
	return llmagent.New(llmagent.Config{
		Name:        "execution_agent",
		Model:       llm,
		Description: "Prepares execution checklist and records the plan.",
		Instruction: strings.TrimSpace(`
Summarize the execution approach, then call log_trade_decision to persist the plan.
Return JSON with:
  - venue_preference
  - order_type
  - timing_notes
  - logging_status
`),
		Tools: []tool.Tool{logTool},
	})
}

func newRootAgent(cfg Config, llm model.LLM, subAgents ...agent.Agent) (agent.Agent, error) {
	tools := make([]tool.Tool, 0, len(subAgents))
	for _, sub := range subAgents {
		tools = append(tools, agenttool.New(sub, nil))
	}

	instruction := strings.TrimSpace(fmt.Sprintf(`
You are the primary orchestrator for %s.
Process flow:
  1. Delegate to research_agent to understand symbol state.
  2. Delegate to signal_agent to draft the trade idea.
  3. Delegate to risk_agent to validate risk parameters.
  4. Delegate to execution_agent to log the plan.
Only approve trades when risk_agent returns decision "APPROVE".
Final reply must be JSON with keys:
  - symbol
  - trade_summary
  - risk
  - execution
  - next_steps
Ensure the narrative references quantitative metrics retrieved from tools.
`, cfg.AppName))

	return llmagent.New(llmagent.Config{
		Name:        fmt.Sprintf("%s_root_agent", sanitizeName(cfg.AppName)),
		Model:       llm,
		Description: "Coordinates multi-agent trading evaluation loop.",
		Instruction: instruction,
		Tools:       tools,
		SubAgents:   subAgents,
	})
}

func sanitizeName(name string) string {
	clean := strings.ReplaceAll(strings.ToLower(name), " ", "_")
	clean = strings.ReplaceAll(clean, string(filepath.Separator), "_")
	return clean
}
