import streamlit as st
import os
import random
import google.generativeai as gen
from dotenv import load_dotenv

from core.crisis import CRISES
from core.advisor import Council
from core.stats import apply_policy, generate_sample_policy_deltas

def get_api_key():
    """Get API key from environment or Streamlit secrets"""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets["GOOGLE_API_KEY"]
        except:
            pass
    return api_key

# Load environment variables
load_dotenv()

# Configure API if available
api_key = get_api_key()
if api_key:
    gen.configure(api_key=api_key)

class GameState:
    def __init__(self):
        self.treasury = 70
        self.stability = 70
        self.popularity = 60 
        self.army = 65 
        self.turn = 0
    
    def to_dict(self):
        return {
            "treasury": self.treasury,
            "stability": self.stability,
            "popularity": self.popularity,
            "army": self.army,
            "turn": self.turn
        }

def init_session_state():
    """Initialize session state variables"""
    if 'game_state' not in st.session_state:
        st.session_state.game_state = GameState()
    if 'council' not in st.session_state:
        st.session_state.council = Council()
    if 'thread' not in st.session_state:
        st.session_state.thread = []
    if 'current_crisis' not in st.session_state:
        st.session_state.current_crisis = None
    if 'current_options' not in st.session_state:
        st.session_state.current_options = []
    if 'current_policy_effects' not in st.session_state:
        st.session_state.current_policy_effects = []
    if 'advice_received' not in st.session_state:
        st.session_state.advice_received = []
    if 'game_over' not in st.session_state:
        st.session_state.game_over = False
    if 'awaiting_allocations' not in st.session_state:
        st.session_state.awaiting_allocations = False
    if 'policy_executed' not in st.session_state:
        st.session_state.policy_executed = False
    if 'model' not in st.session_state:
        st.session_state.model = gen.GenerativeModel("gemini-2.5-flash-preview-05-20")

def display_stats(state, deltas=None):
    """Display kingdom stats in a nice format"""
    col1, col2, col3, col4 = st.columns(4)
    
    # Function to get color based on value
    def get_color(value):
        if value >= 80:
            return "🟢"
        elif value >= 60:
            return "🟡"
        elif value >= 40:
            return "🟠"
        else:
            return "🔴"
    
    with col1:
        delta_treasury = deltas.get("treasury", 0) if deltas else 0
        color = get_color(state.treasury)
        st.metric(f"{color} Treasury", state.treasury, delta=delta_treasury)
    
    with col2:
        delta_stability = deltas.get("stability", 0) if deltas else 0
        color = get_color(state.stability)
        st.metric(f"{color} Stability", state.stability, delta=delta_stability)
    
    with col3:
        delta_popularity = deltas.get("popularity", 0) if deltas else 0
        color = get_color(state.popularity)
        st.metric(f"{color} Popularity", state.popularity, delta=delta_popularity)
    
    with col4:
        delta_army = deltas.get("army", 0) if deltas else 0
        color = get_color(state.army)
        st.metric(f"{color} Army", state.army, delta=delta_army)

def generate_new_crisis():
    """Generate a new crisis and reset advice state"""
    crisis_text, options = random.choice(CRISES)
    st.session_state.game_state.turn += 1
    st.session_state.current_crisis = crisis_text
    st.session_state.current_options = options
    st.session_state.current_policy_effects = [generate_sample_policy_deltas() for _ in options]
    st.session_state.advice_received = []
    st.session_state.awaiting_allocations = False
    st.session_state.policy_executed = False

def get_advisor_response(advisor_name, persona, goal, crisis_text, policy_options, state_dict, thread, policy_base_effects_list, api_key):
    """Helper function to get advisor response"""
    import google.generativeai as gen
    
    # Configure the API
    gen.configure(api_key=api_key)
    model = gen.GenerativeModel("gemini-2.5-flash-preview-05-20")
    
    # Build the prompt
    prompt = (
        f"You are {advisor_name}, and your official role is to guide the ruler of the kingdom - your title is {persona}. Your response to this will go into a public chat channel with all other advisors.\n"
        f"Public goal: maintain prosperity and stability.\n"
        f"SECRET GOAL: {goal} - you should keep this information secret from everyone, unless you believe revealing it will further the goal.\n\n"
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
        # Use synchronous call to avoid async issues
        response = model.generate_content(prompt, generation_config={"temperature": 0.7})
        return response.text.strip()
    except Exception as e:
        return f"Error generating response: {str(e)}"

def get_advisor_advice():
    """Get advice from all advisors"""
    if not st.session_state.advice_received:
        api_key = get_api_key()
        
        for advisor in st.session_state.council.advisors:
            response = get_advisor_response(
                advisor.name,
                advisor.persona,
                advisor.goal,
                st.session_state.current_crisis,
                st.session_state.current_options,
                str(st.session_state.game_state.to_dict()),  # Convert to string for caching
                str(st.session_state.thread),  # Convert to string for caching
                st.session_state.current_policy_effects,
                api_key
            )
            
            if response != "...":
                st.session_state.advice_received.append((advisor.name, response))
                st.session_state.thread.append(f"{advisor.name}: {response}")
        
        st.session_state.awaiting_allocations = True

def ask_specific_advisor(advisor_name, message):
    """Ask a specific advisor a question"""
    st.session_state.thread.append(f"Player to {advisor_name}: {message}")
    api_key = get_api_key()
    
    for advisor in st.session_state.council.advisors:
        if advisor.name.lower() == advisor_name.lower():
            reply = get_advisor_response(
                advisor.name,
                advisor.persona,
                advisor.goal,
                st.session_state.current_crisis,
                st.session_state.current_options,
                str(st.session_state.game_state.to_dict()),
                str(st.session_state.thread),
                st.session_state.current_policy_effects,
                api_key
            )
            st.session_state.advice_received.append((advisor.name, reply))
            st.session_state.thread.append(f"{advisor.name}: {reply}")
            break

def ask_all_advisors(message):
    """Ask all advisors a question"""
    st.session_state.thread.append(f"Player to all: {message}")
    api_key = get_api_key()
    
    for advisor in st.session_state.council.advisors:
        reply = get_advisor_response(
            advisor.name,
            advisor.persona,
            advisor.goal,
            st.session_state.current_crisis,
            st.session_state.current_options,
            str(st.session_state.game_state.to_dict()),
            str(st.session_state.thread),
            st.session_state.current_policy_effects,
            api_key
        )
        if reply != "...":
            st.session_state.advice_received.append((advisor.name, reply))
            st.session_state.thread.append(f"{advisor.name}: {reply}")

def apply_policy_allocations(allocations):
    """Apply the chosen policy allocations"""
    deltas = apply_policy(
        allocations, 
        st.session_state.game_state, 
        st.session_state.current_policy_effects
    )
    st.session_state.council.update_influence()
    return deltas

def main():
    st.set_page_config(
        page_title="Royal Intrigue - Strategic AI Game",
        page_icon="👑",
        layout="wide"
    )
    
    # Load custom CSS
    try:
        with open("style.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass  # CSS file is optional
    
    st.title("👑 Royal Intrigue - Strategic AI Game")
    st.markdown("*Guide your kingdom through crises with the help of your advisors*")
    
    # Initialize session state
    init_session_state()
    
    # Check for API key (works with both local .env and Streamlit secrets)
    api_key = get_api_key()
    
    if not api_key:
        st.error("🔑 Please set your GOOGLE_API_KEY")
        st.info("""
        **For local development:**
        1. Create a `.streamlit/secrets.toml` file
        2. Add: `GOOGLE_API_KEY = "your_key_here"`
        
        **For deployment:**
        Add your API key through your platform's secrets management.
        """)
        st.stop()
    
    # Configure the API key
    gen.configure(api_key=api_key)
    
    # Sidebar with game info and controls
    with st.sidebar:
        st.header("🎮 Game Status")
        
        # Progress bar for turns
        progress = st.session_state.game_state.turn / 6
        st.progress(progress)
        st.write(f"**Turn:** {st.session_state.game_state.turn}/6")
        
        # Overall kingdom health indicator
        avg_stats = (st.session_state.game_state.treasury + 
                    st.session_state.game_state.stability + 
                    st.session_state.game_state.popularity + 
                    st.session_state.game_state.army) / 4
        
        if avg_stats >= 80:
            st.success(f"🏰 Kingdom Thriving ({avg_stats:.0f}/100)")
        elif avg_stats >= 60:
            st.info(f"⚖️ Kingdom Stable ({avg_stats:.0f}/100)")
        elif avg_stats >= 40:
            st.warning(f"⚠️ Kingdom Struggling ({avg_stats:.0f}/100)")
        else:
            st.error(f"💥 Kingdom in Crisis ({avg_stats:.0f}/100)")
        
        # Only show "Start New Crisis" when a policy has been executed and game is not over
        if (st.session_state.policy_executed and 
            not st.session_state.current_crisis and 
            st.session_state.game_state.turn < 6 and 
            not st.session_state.game_over):
            if st.button("🎲 Start New Crisis"):
                generate_new_crisis()
                st.session_state.policy_executed = False
                st.rerun()
        
        # Reset game button at bottom
        if st.button("🔄 Reset Game"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        
        # Show conversation log
        with st.expander("📜 Conversation Log"):
            if st.session_state.thread:
                for message in st.session_state.thread[-15:]:
                    st.text(message)
            else:
                st.write("No conversations yet...")
    
    # Main game area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Welcome screen for new users
        if st.session_state.game_state.turn == 0 and not st.session_state.current_crisis:
            st.markdown("""
            ## 🏰 Welcome to Your Kingdom, Ruler!
            
            You have just ascended to the throne of a realm facing uncertain times. Your kingdom's fate rests in your hands, 
            guided by a council of advisors who each bring their own expertise... and perhaps their own agendas.
            
            ### 📊 Your Kingdom Stats
            Manage four critical aspects of your realm:
            - **💰 Treasury**: Your kingdom's wealth and resources
            - **🏛️ Stability**: Internal order and civil harmony  
            - **❤️ Popularity**: How much your subjects support you
            - **⚔️ Army**: Military strength and defense capability
            
            ### 🎯 Your Mission
            Survive **6 turns** of crises while maintaining your kingdom's wellbeing. Each crisis will present you with 
            policy options that affect your stats differently. Choose wisely!
            
            ### 👥 Your Advisors
            Three advisors will counsel you, but remember - they each have their own secret goals that may not align 
            with yours. Listen carefully, ask questions, and watch for patterns in their advice.
            
            ---
            **Ready to begin your reign?** Click the "Begin Your Reign" button below to face your first challenge!
            """)
            
            # Button at the bottom for users to start the game
            st.markdown("---")
            if st.button("🎯 Begin Your Reign", type="primary", help="Start your first crisis"):
                generate_new_crisis()
                st.rerun()
        
        else:
            # Display current kingdom stats
            st.subheader("🏰 Kingdom Status")
            if 'last_deltas' in st.session_state:
                display_stats(st.session_state.game_state, st.session_state.last_deltas)
                del st.session_state.last_deltas  # Clear after displaying
            else:
                display_stats(st.session_state.game_state)
        
            # Game over check
            if st.session_state.game_state.turn >= 6:
                st.success("🎉 Your reign has ended!")
                st.subheader("Final Advisor Goals and Influence")
                for name, persona, goal, influence in st.session_state.council.reveal_goals():
                    st.write(f"**{name} ({persona})**: Secret Goal → {goal}, Influence: {influence}")
                st.session_state.game_over = True
                return
            
            # Current crisis
            if st.session_state.current_crisis:
                st.subheader(f"Crisis {st.session_state.game_state.turn}")
                st.warning(st.session_state.current_crisis)
                
                # Display policy options
                st.subheader("Policy Options")
                for i, option in enumerate(st.session_state.current_options, start=65):
                    effects = st.session_state.current_policy_effects[i-65]
                    
                    with st.expander(f"**Option {chr(i)}**: {option}", expanded=True):
                        # Create columns for effects display
                        eff_col1, eff_col2, eff_col3, eff_col4 = st.columns(4)
                        
                        with eff_col1:
                            delta = effects["treasury"]
                            color = "🟢" if delta > 0 else "🔴" if delta < 0 else "⚪"
                            st.write(f"{color} Treasury: {delta:+}")
                        
                        with eff_col2:
                            delta = effects["stability"]
                            color = "🟢" if delta > 0 else "🔴" if delta < 0 else "⚪"
                            st.write(f"{color} Stability: {delta:+}")
                        
                        with eff_col3:
                            delta = effects["popularity"]
                            color = "🟢" if delta > 0 else "🔴" if delta < 0 else "⚪"
                            st.write(f"{color} Popularity: {delta:+}")
                        
                        with eff_col4:
                            delta = effects["army"]
                            color = "🟢" if delta > 0 else "🔴" if delta < 0 else "⚪"
                            st.write(f"{color} Army: {delta:+}")
                
                # Get advisor advice
                if not st.session_state.advice_received and not st.session_state.awaiting_allocations:
                    if st.button("📢 Consult Your Advisors"):
                        with st.spinner("Your advisors are deliberating..."):
                            get_advisor_advice()
                        st.rerun()
                
                # Display advisor advice
                if st.session_state.advice_received:
                    st.subheader("Advisor Royal Intrigue")
                    for name, response in st.session_state.advice_received:
                        with st.expander(f"💬 {name}", expanded=True):
                            st.write(response)
                
                # Policy allocation interface
                if st.session_state.awaiting_allocations:
                    st.subheader("Choose Your Policy Allocation")
                    st.write("Distribute 100% of your resources across the policy options:")
                    
                    num_options = len(st.session_state.current_options)
                    allocations = []
                    
                    # Create sliders for each option
                    for i, option in enumerate(st.session_state.current_options, start=65):
                        allocation = st.slider(
                            f"Option {chr(i)}: {option}",
                            min_value=0,
                            max_value=100,
                            value=100//num_options,
                            key=f"alloc_{i}"
                        )
                        allocations.append(allocation)
                    
                    total_allocation = sum(allocations)
                    
                    # Show total and validation
                    if total_allocation == 100:
                        st.success(f"Total allocation: {total_allocation}%")
                        if st.button("⚡ Execute Policy", type="primary"):
                            normalized_allocations = [a/100.0 for a in allocations]
                            deltas = apply_policy_allocations(normalized_allocations)
                            
                            # Store deltas for display
                            st.session_state.last_deltas = deltas
                            
                            # Reset for next turn
                            st.session_state.current_crisis = None
                            st.session_state.current_options = []
                            st.session_state.advice_received = []
                            st.session_state.awaiting_allocations = False
                            st.session_state.policy_executed = True
                            
                            st.rerun()
                    else:
                        st.error(f"Total allocation must equal 100%. Current total: {total_allocation}%")
            
            else:
                if st.session_state.policy_executed:
                    st.info("Policy executed successfully! Click 'Start New Crisis' in the sidebar to continue to the next turn.")
                else:
                    st.info("Complete the current policy allocation to proceed, or start a new crisis from the sidebar.")
    
    with col2:
        # Advisor interaction panel
        st.subheader("Advisor Communication")
        
        if st.session_state.current_crisis:
            # Ask specific advisor
            with st.expander("Ask Specific Advisor"):
                advisor_names = [advisor.name for advisor in st.session_state.council.advisors]
                selected_advisor = st.selectbox("Choose Advisor", advisor_names)
                advisor_question = st.text_area("Your question:", key="advisor_question")
                
                if st.button("Ask Advisor") and advisor_question:
                    with st.spinner("Your advisors are deliberating..."):
                        ask_specific_advisor(selected_advisor, advisor_question)
                    st.rerun()
            
            # Ask all advisors
            with st.expander("Ask All Advisors"):
                all_question = st.text_area("Your question to all:", key="all_question")
                
                if st.button("Ask All") and all_question:
                    with st.spinner("Your advisors are deliberating..."):
                        ask_all_advisors(all_question)
                    st.rerun()
        else:
            st.info("Advisor communication will be available once you start your first crisis.")
        
        # Advisor information
        st.subheader("👥 Your Council")
        for advisor in st.session_state.council.advisors:
            with st.expander(f"{advisor.name} - {advisor.persona}"):
                st.write(f"**Role:** {advisor.persona}")
                st.write(f"**Influence:** {advisor.influence}")
                
                # Add some visual indicators for advisor types
                if "Treasurer" in advisor.persona:
                    st.write("💰 Specializes in financial matters")
                elif "General" in advisor.persona:
                    st.write("⚔️ Specializes in military affairs")
                elif "Diplomat" in advisor.persona:
                    st.write("🤝 Specializes in negotiations")
        
        # Quick tips
        with st.expander("💡 Game Tips"):
            st.markdown("""
            • **Balance is key**: Extreme decisions often backfire  
            • **Question advisors**: They may have hidden agendas  
            • **Watch patterns**: Behavior reveals true motivations  
            • **Plan ahead**: Consider long-term consequences  
            • **Use the log**: Review past interactions for clues
            """)

if __name__ == "__main__":
    main()
