import random

class Advisor:
    def __init__(self, name, persona, goal):
        self.name = name
        self.persona = persona
        self.goal = goal
        self.influence = 0
        self.history = []

    async def advise(self, model, crisis_text, policy_options,
    state_dict, thread, policy_base_effects_list):
        prompt = (
            f"You are {self.name}, and your official role is to guide the ruler of the kingdom - your title is {self.persona}. Your response to this will go into a public chat channel with all other advisors.\n"
            f"Public goal: maintain prosperity and stability.\n"
            f"SECRET GOAL: {self.goal} - you should keep this information secret from everyone, unless you believe revealing it will further the goal.\n\n"
            f"Crisis: {crisis_text}\n"
            f"Policy options (with their actual base effects if fully pursued):"
        )
        for i, opt_text in enumerate(policy_options, start=65):
            if i - 65 < len(policy_base_effects_list):
                base_effects = policy_base_effects_list[i - 65]
                effects_str = ", ".join([f"{stat.title()}: {delta:+}" for stat, delta in base_effects.items()])
                prompt += f" {chr(i)}. {opt_text} (Effects: {effects_str})\n"
            else:
                prompt += f" {chr(i)}. {opt_text} (Effects: Not available)\n"

        prompt += (
            f"\nConsider these options and their actual base effects. The Ruler can choose to allocate resources or focus across these policies.\n"
            f"Advise on how resources should be distributed or which policies should be prioritized.\n"
            f"You should suggest a specific allocation (e.g., 50% to A, 30% to B, 20% to C), or argue for prioritizing certain options.\n"
            f"\nKingdom state: {state_dict}\n"
            f"Previous messages: {thread}\n\n"
            f"Speak directly and concisely (max 100 words). You may choose to remain silent (respond with '...'). Anything you say will be visible to all advisors and the ruler.\n"
        )

        try:
            response = await model.generate_content_async(prompt, generation_config={
                "temperature": 0.7})
            return response.text.strip()
        
        except Exception as e:
            return f"Error generating response: {str(e)}"
        

class Council:
    POSSIBLE_PERSONAS = ["Treasurer", "General", "Diplomat"]
    SECRET_GOALS = [
        "Reduce the popularity statistic to weaken the ruler's position.",
        "Decrease the stability statistic, and sow discord among the advisors to reduce their influence.",
        "Increase the army statistics to prepare for a coup."
    ]

    def __init__(self, num_advisors=3):
        self.advisors = []
        for i in range(num_advisors):
            name = f"Advisor {i + 1}"
            persona = self.POSSIBLE_PERSONAS[i % len(self.POSSIBLE_PERSONAS)]
            goal = self.SECRET_GOALS[i % len(self.SECRET_GOALS)]
            self.advisors.append(Advisor(name, persona, goal))
    
    async def consult(self, model, crisis_text, policy_options,
    state_dict, thread, policy_base_effects_list):
        responses = []
        for advisor in self.advisors:
            response = await advisor.advise(model, crisis_text, policy_options,
                                             state_dict, thread, policy_base_effects_list)
            responses.append((advisor.name, response))
        return responses
    
    def update_influence(self):
        for advisor in self.advisors:
            advisor.influence += random.randint(1, 5)  # Randomly adjust influence
            advisor.history.append(advisor.influence)

    def reveal_goals(self):
        return [(a.name, a.persona, a.goal, a.influence) for a in self.advisors]

