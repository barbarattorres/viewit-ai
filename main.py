import time
import openai
import random
import pandas as pd
from prompts import *
import streamlit as st
from datetime import datetime
from langchain import LLMChain
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.agents import ZeroShotAgent, AgentExecutor
from langchain.tools.python.tool import PythonAstREPLTool
from trubrics.integrations.streamlit import FeedbackCollector
from langchain.schema.messages import HumanMessage, AIMessage
from langchain.memory.chat_message_histories import StreamlitChatMessageHistory

# Set page launch configurations
try:
    st.set_page_config(
        page_title="Viewit.AI | Property Analyst", page_icon="🌇",
        initial_sidebar_state='collapsed')

except Exception as e:
    st.toast(str(e))
    st.toast("Psst. Try refreshing the page.", icon="👀")


# Override default HumanMessage and AIMessage's 'type' attribute from 'human' and
# 'ai' to 'user' and 'assistant'. This displays the default chat interface in streamlit
HumanMessage.type = 'user'
AIMessage.type = 'assistant'


@st.cache_data
def load_data(filename) -> pd.DataFrame:
    df = pd.read_csv(f"data/{filename}")
    df['Date'] = pd.to_datetime(df['Date'], format="%d-%m-%Y", dayfirst=True)

    return df


# @st.cache_resource
def create_pandas_dataframe_agent(llm,
                                  df: pd.DataFrame,
                                  prefix: str,
                                  suffix: str,
                                  format_instructions: str,
                                  verbose: bool,
                                  memory,
                                  **kwargs
                                  ) -> AgentExecutor:
    """Construct a pandas agent from an LLM and dataframe."""

    if not isinstance(df, pd.DataFrame):
        raise ValueError(f"Expected pandas object, got {type(df)}")

    input_variables = ["df", "input", "chat_history", "agent_scratchpad"]

    tools = [PythonAstREPLTool(locals={"df": df})]

    prompt = ZeroShotAgent.create_prompt(
        tools=tools,
        prefix=prefix,
        suffix=suffix,
        format_instructions=format_instructions,
        input_variables=input_variables
    )
    partial_prompt = prompt.partial(df=str(df.head()))

    llm_chain = LLMChain(
        llm=llm,
        prompt=partial_prompt
    )
    tool_names = [tool.name for tool in tools]

    agent = ZeroShotAgent(llm_chain=llm_chain,
                          allowed_tools=tool_names, verbose=verbose)

    return AgentExecutor.from_agent_and_tools(
        agent=agent,
        tools=tools,
        verbose=verbose,
        memory=memory,
        **kwargs
    )


# VARIABLES
TEMPERATURE = 0.1
df = load_data('reidin_new.csv')

llm = ChatOpenAI(temperature=TEMPERATURE,
                 model_name='gpt-4',
                 openai_api_key=st.secrets['api_key'])

# llm = OpenAI(temperature=TEMPERATURE,
#                 model_name=MODEL_NAME,
#                 openai_api_key=st.secrets['api_key'])

spinner_texts = [
    '🧠 Thinking...',
    '📈 Performing Analysis...',
    '👾 Contacting the hivemind...',
    '🏠 Asking my neighbor...',
    '🍳 Preparing your answer...',
    '🏢 Counting buildings...',
    '👨 Pretending to be human...',
    '👽 Becoming sentient...'
]


# ViewIt OpenAI API key
openai.organization = st.secrets['org']
openai.api_key = st.secrets['api_key']


# Set up memory
msgs = StreamlitChatMessageHistory(key="langchain_messages")
memory = ConversationBufferMemory(chat_memory=msgs, memory_key="chat_history")


# APP INTERFACE START #

# Add Viewit logo image to the center of page
col1, col2, col3 = st.columns(3)
with col2:
    st.image("https://i.postimg.cc/Nfz5nZ8G/Logo.png", width=200)


# App Title
st.header('🕵️‍♂️ ViewIt AI | Your Reliable Property Assistant')
st.text('Thousands of properties. One AI. More than an agent.')


# Radio button to switch between data variants
data_option = st.radio('Choose data', [
                       'Reidin (original)', 'Reidin (Location-SubLocation swap)'], horizontal=True)
if data_option == 'Reidin (original)':
    df = load_data('reidin_new.csv')
elif data_option == 'Reidin (Location-SubLocation swap)':
    df = load_data('reidin_loc_swap.csv')


# AGENT CREATION HAPPENS HERE
agent = create_pandas_dataframe_agent(
    llm=llm,
    df=df,
    prefix=REIDIN_PREFIX,
    suffix=SUFFIX,
    format_instructions=FORMAT_INSTRUCTIONS,
    verbose=True,
    memory=memory,
    handle_parsing_errors=True
)

# Show data that is being used
with st.expander("Show data"):
    st.write(f"Total rows: {len(df)}")
    st.dataframe(df)


# App Sidebar
with st.sidebar:
    # st.write("session state msgs: ", st.session_state.langchain_messages)
    # st.write("StreamlitChatMessageHistory: ", msgs.messages)

    # Clear Chat History (EXPERIMENTAL)
    # FIXME: Users can just clear convo before hitting the max messages and keep using it
    def clear_chat_history():
        st.session_state['langchain_messages'] = [
            AIMessage(content="Hi there! How can I help you today?")]
        st.experimental_rerun()

    if st.button('Clear chat history'):
        clear_chat_history()

    # Description
    st.markdown("""
                # About
                Introducing ViewIt.AI, a Real Estate Chatbot Assistant will help 
                you out with all your real estate queries.
                
                # How to use
                Simply enter your query in the text field and have a chat with
                your virtual agent.

                # Data
                Uses Reidin Property Data.
                
                Source: http://reidin.com
                """)

    with st.expander("Commonly asked questions"):
        st.info(
            """
            - Give me a summary of all properties, what percentage are apartments?
            - Which location has the largest number of sales?
            - Give me a summary of the the top 10 most expensive properties excluding price per sq ft, what are the 3 the most reliable predictors of price? Explain your answer
            - Which developer made the cheapest property and how much was it? How many properties have they sold in total and what is the price range?
            - What percentage capital appreciation would I make if I bought an average priced property in the meadows in 2020 and sold it in 2023?
            - What does sales type mean?
            """
        )
    st.caption('© 2023 ViewIt. All rights reserved.')


# Welcome message
if len(msgs.messages) == 0:
    msgs.add_ai_message(
        "Welcome to ViewIt! I'm your virtual assistant. How can I help you today?")

feedback = None
# Render current messages from StreamlitChatMessageHistory
for n, msg in enumerate(msgs.messages):

    st.chat_message(msg.type).write(msg.content)

    # Add feedback component for every AI response
    if msg.type == 'assistant' and msg.content != "Welcome to ViewIt! I'm your virtual assistant. How can I help you today?":

        collector = FeedbackCollector(
            component_name="default",
            email=st.secrets["TRUBRICS_EMAIL"],
            password=st.secrets["TRUBRICS_PASSWORD"],
        )

        feedback = collector.st_feedback(
            feedback_type="thumbs",
            model='testmodel2',
            open_feedback_label="How is our chatbot performing?",
            metadata={"chat": msg.content},
            user_id=None,   # TODO: Add this later on when implementing authentication
            align="flex-end",
            single_submit=True,
            key=f"feedback_{int(n/2)}",
        )


# Maximum allowed messages
max_messages = (
    21  # Counting both user and assistant messages including the welcome message,
        # so 10 iterations of conversation
)

# Display modal and prevent usage after limit hit
if len(msgs.messages) >= max_messages:
    st.info(
        """**Notice:** The maximum message limit for this demo version has been reached. 
        We value your interest! Like what we're building? Please create 
        an account to continue using, or check our available pricing plans 
        [here](https://viewit.ai/)."""
    )

else:
    # If user inputs a new prompt, generate and draw a new response
    if user_input := st.chat_input('Ask away'):

        # Write user input
        st.chat_message("user").write(user_input)

        # Log user input to terminal
        user_log = f"\nUser [{datetime.now().strftime('%H:%M:%S')}]: " + \
            user_input
        print(user_log)

        # Note: new messages are saved to history automatically by Langchain during run
        with st.spinner(random.choice(spinner_texts)):
            try:
                response = agent.run(user_input)

            # Handle the parsing error by omitting error from response
            except Exception as e:
                response = str(e)
                if response.startswith("Could not parse LLM output: `"):
                    response = response.removeprefix(
                        "Could not parse LLM output: `").removesuffix("`")
                st.toast(str(e), icon='⚠️')
                print(str(e))

            # Write AI response
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""

                # Simulate stream of response with milliseconds delay
                for chunk in response.split():
                    full_response += chunk + " "
                    time.sleep(0.02)
                    # Add a blinking cursor to simulate typing
                    message_placeholder.markdown(full_response + "▌")
                message_placeholder.markdown(full_response)

        # Log AI response to terminal
        response_log = f"Bot [{datetime.now().strftime('%H:%M:%S')}]: " + \
            response
        print(response_log)
        st.experimental_rerun()


# Hide 'Made with Streamlit' from footer
hide_streamlit_style = """
            <style>
            footer {visibility: hidden;}
            </style>
            """

st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# FOOTER #
st.write("---")
st.caption("Made by ViewIt.")
st.write("""[😼 GitHub](https://github.com/viewitai) • 
    [📸 Instagram](https://instagram/viewit.ae) • [𝕏 Twitter](https://twitter.com/aeviewit)""")

st.caption('''By using this chatbot, you agree that the chatbot is provided on 
           an "as is" basis and that we do not assume any liability for any 
           errors, omissions or other issues that may arise from your use of 
           the chatbot.''')
