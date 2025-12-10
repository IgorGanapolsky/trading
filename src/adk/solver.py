import asyncio
import json
import logging
import os
import sys

# Ensure src is in path
sys.path.append(os.getcwd())

from src.adk import LlmAgent, ParallelAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ADK_Solver")


async def main(goal: str):
    print(f"\n🚀 ADK Auto-Solver: Parallelizing task '{goal}'...\n")

    # --- Step 1: Planning (Decomposition) ---
    planner_instructions = (
        "You are a Senior Project Manager. Break the user's complex goal into 2-4 distinct, "
        "independent sub-tasks that can be researched or executed in parallel. "
        'Return ONLY a raw JSON list of strings, e.g., ["Research X", "Analyze Y"]. '
        "Do not include markdown formatting or explanations."
    )

    planner = LlmAgent(
        name="Planner",
        model_name="gemini-2.0-flash-exp",
        instructions=planner_instructions,
        temperature=0.2,
        max_retries=5,
    )

    logger.info("Planning decomposition...")
    try:
        plan_text = await planner.run(goal, context={})
        # Clean potential markdown code blocks
        plan_text = plan_text.replace("```json", "").replace("```", "").strip()
        subtasks = json.loads(plan_text)

        if not isinstance(subtasks, list):
            raise ValueError("Planner did not return a list.")

        print(f"📋 Plan: {subtasks}")

    except Exception as e:
        logger.error(f"Planning failed: {e}. Fallback to single agent.")
        subtasks = [goal]

    # --- Step 2: Parallel Execution ---
    workers = {}
    for i, task in enumerate(subtasks):
        worker_name = f"Worker_{i + 1}"
        workers[worker_name] = LlmAgent(
            name=worker_name,
            model_name="gemini-2.0-flash-exp",
            instructions="You are an expert researcher. detailed, factual, and concise.",
            temperature=0.7,
            max_retries=5,
        )

    # Use max_concurrency=2 to be safe but faster than 1
    ParallelAgent(name="ResearchSwarm", agents=workers, max_concurrency=2)

    logger.info(f"Spinning up {len(workers)} parallel agents...")

    # Create a semaphore for rate limiting
    semaphore = asyncio.Semaphore(2)

    async def run_worker(name, agent, task_input):
        async with semaphore:
            logger.info(f"Starting {name} on: {task_input}")
            return await agent.run(task_input, context={})

    tasks = [
        run_worker(name, agent, subtasks[i]) for i, (name, agent) in enumerate(workers.items())
    ]
    results_list = await asyncio.gather(*tasks)

    results_dict = dict(zip(workers.keys(), results_list, strict=False))

    # --- Step 3: Synthesis ---
    synthesizer = LlmAgent(
        name="Synthesizer",
        model_name="gemini-2.0-flash-exp",
        instructions="You are a Chief Architect. Synthesize the provided reports into a single, cohesive, actionable answer to the original goal.",
        temperature=0.5,
        max_retries=5,
    )

    synthesis_prompt = f"Original Goal: {goal}\n\n"
    for name, result in results_dict.items():
        synthesis_prompt += f"--- Report from {name} ---\n{result}\n\n"

    logger.info("Synthesizing results...")
    final_answer = await synthesizer.run(synthesis_prompt, context={})

    print("\n✅ --- FINAL RESULT ---")
    print(final_answer)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/adk/solver.py '<task_description>'")
        sys.exit(1)

    if not os.environ.get("GOOGLE_API_KEY"):
        print("Error: GOOGLE_API_KEY environment variable not set.")
        sys.exit(1)

    user_goal = sys.argv[1]
    asyncio.run(main(user_goal))
