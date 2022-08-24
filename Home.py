import streamlit as st
from PIL import Image




def run():
    # favicon image
    im = Image.open("favicon.ico")

    st.set_page_config(
        page_title="Marketing Tools for NLP Analytics",
        page_icon=im,
    )

    st.write("# Welcome to Marketing Tools! 🕵️‍♂️")

    st.sidebar.success("Select a page above")

    st.markdown(
        """
        ### Overview
        Marketing tools are intended to help and equip marketing team with cutting-edge machine learning and automation technology.
        By using these tools in daily basis, team can make their tasks a lot easier.
        **👈 Select a from the sidebar** to see use tools
        ### Sources of Data
        User of these tools should prepare their own files before uploading here and then to proceed according to their needs.
        - __Phone Converter__
        Phone converter tool is used for converting unstructured phone format into clean ones. This step is required to fit phone format with blast message tool through WhatsApp API
        - __Chatlog Summarizer__
        The function of chatlog summarizer help us identify and categorize the contents of a message and get the sentiment automatically.
        
    """
    )


if __name__ == "__main__":
    run()
