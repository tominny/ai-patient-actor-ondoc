# Medical Education AI Feedback Analysis

## Overview

This repository contains a Python script for analyzing student feedback on AI-based clinical learning tools using Natural Language Processing (NLP) and OpenAI's GPT-4. The tool was developed for a medical education research project that evaluated student perceptions of an AI Patient Actor application used for clinical communication training.

## Features

- Extracts text from PDF documents containing student feedback
- Preprocesses and tokenizes text into individual sentences
- Classifies each sentence into predefined thematic categories using GPT-4
- Generates visualization of thematic distributions
- Outputs detailed JSON results for further analysis

## Requirements

- Python 3.6+
- OpenAI API key
- Required Python packages:
  - `matplotlib`
  - `openai`
  - `pdfminer.six`
  - `nltk`
  - `numpy`
  - `seaborn`
  - `pandas`

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/med-ed-ai-feedback-analysis.git
   cd med-ed-ai-feedback-analysis
   ```

2. Install required packages:
   ```
   pip install -r requirements.txt
   ```

3. Set up your OpenAI API key:
   - Create a `.env` file with your API key:
     ```
     OPENAI_API_KEY=your_api_key_here
     ```
   - Or modify the script to use your API key directly (not recommended for public repositories)

## Usage

1. Update the `pdf_path` variable in the script to point to your PDF file containing student feedback:
   ```python
   pdf_path = '/path/to/your/feedback.pdf'
   ```

2. Run the script:
   ```
   python analysis.py
   ```

3. The script will:
   - Extract and preprocess text from the PDF
   - Classify each sentence into one of the predefined themes
   - Save the classification results to `thematic_analysis_results.json`
   - Generate and save a visualization to `thematic_analysis_plot.png`

## Predefined Themes

The script classifies student feedback into six themes:

1. Opportunities for Practice and Reflection
2. Effective Immediate Feedback
3. Technical Issues and Frustrations
4. Enhanced Clinical Reasoning and Diagnostic Skills
5. Utility in Practicing Clinical Write-Ups
6. Limitations in Simulating Real Interactions

Sentences that cannot be confidently categorized are labeled as "Uncategorized".

## License

MIT License

# ai-patient-actor-ondoc
