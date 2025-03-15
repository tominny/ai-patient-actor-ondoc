import sys
import re
import matplotlib.pyplot as plt
import openai
from pdfminer.high_level import extract_text
import nltk
import json
import pkg_resources
import time

# For plotting
import numpy as np
import seaborn as sns
import pandas as pd

# Check openai version
openai_version = pkg_resources.get_distribution("openai").version
is_old_api = int(openai_version.split('.')[0]) < 1

# Download NLTK data files (only need to run once)
nltk.download('punkt', quiet=True)

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file."""
    try:
        text = extract_text(pdf_path)
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        sys.exit(1)

def preprocess_text(text):
    """Preprocess text by tokenizing sentences and cleaning."""
    # Split text into sentences
    sentences = nltk.sent_tokenize(text)
    # Remove numbering and extra whitespace
    sentences = [re.sub(r'^\d+\.\s*', '', sent).strip() for sent in sentences if sent.strip()]
    return sentences

def classify_sentence(sentence, client=None):
    """Classify a single sentence using OpenAI GPT-4."""
    # Prepare the prompt for GPT-4 with predefined themes
    prompt = (
        "Classify the following student evaluation about an AI-based clinical learning tool into exactly one of these themes:\n"
        "1. Opportunities for Practice and Reflection\n"
        "2. Effective Immediate Feedback\n"
        "3. Technical Issues and Frustrations\n"
        "4. Enhanced Clinical Reasoning and Diagnostic Skills\n"
        "5. Utility in Practicing Clinical Write-Ups\n"
        "6. Limitations in Simulating Real Interactions\n\n"
        "If the sentence cannot be confidently categorized into one of these themes, return 'Uncategorized'.\n"
        "Return ONLY the theme name without any additional text or explanation.\n\n"
        f"Student Evaluation: \"{sentence}\""
    )

    try:
        if is_old_api:
            # Use the old OpenAI API syntax (pre-1.0.0)
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an assistant that classifies text into predefined themes."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,  # Short response needed
                temperature=0,
            )
            # Extract the assistant's reply
            theme = response['choices'][0]['message']['content'].strip()
        else:
            # Use the new OpenAI API syntax (1.0.0+)
            if client is None:
                client = openai.OpenAI(api_key=openai.api_key)
                
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an assistant that classifies text into predefined themes."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,  # Short response needed
                temperature=0,
            )
            # Extract the assistant's reply
            theme = response.choices[0].message.content.strip()
            
        # Validate the theme is one of the expected themes
        valid_themes = [
            "Opportunities for Practice and Reflection",
            "Effective Immediate Feedback",
            "Technical Issues and Frustrations",
            "Enhanced Clinical Reasoning and Diagnostic Skills",
            "Utility in Practicing Clinical Write-Ups",
            "Limitations in Simulating Real Interactions"
        ]
        
        # Check if the theme is valid or try to match it to a valid theme
        if theme not in valid_themes:
            # Try to find the closest match
            for valid_theme in valid_themes:
                if valid_theme.lower() in theme.lower():
                    return valid_theme
            # If no match, return "Uncategorized"
            print(f"Could not categorize: '{sentence}', GPT-4 returned: '{theme}'")
            return "Uncategorized"
            
        return theme
        
    except Exception as e:
        print(f"OpenAI API error classifying sentence: {e}")
        return "Uncategorized"

def process_sentences(sentences):
    """Process each sentence individually and classify it into a theme."""
    # Dictionary to store results
    themes = {
        "Opportunities for Practice and Reflection": {"count": 0, "feedback": []},
        "Effective Immediate Feedback": {"count": 0, "feedback": []},
        "Technical Issues and Frustrations": {"count": 0, "feedback": []},
        "Enhanced Clinical Reasoning and Diagnostic Skills": {"count": 0, "feedback": []},
        "Utility in Practicing Clinical Write-Ups": {"count": 0, "feedback": []},
        "Limitations in Simulating Real Interactions": {"count": 0, "feedback": []},
        "Uncategorized": {"count": 0, "feedback": []}
    }
    
    # Initialize OpenAI client if using new API
    client = None
    if not is_old_api:
        client = openai.OpenAI(api_key=openai.api_key)
    
    # Process each sentence
    total = len(sentences)
    for i, sentence in enumerate(sentences):
        # Skip empty sentences
        if not sentence.strip():
            continue
            
        # Print progress
        print(f"Processing sentence {i+1}/{total}: {sentence[:50]}..." + ("" if len(sentence) <= 50 else ""))
        
        # Classify the sentence
        theme = classify_sentence(sentence, client)
        
        # Add to results
        themes[theme]["count"] += 1
        themes[theme]["feedback"].append(sentence)
        
        # Log the classification
        print(f"  → Classified as: {theme}")
        
        # Add a small delay to avoid rate limiting
        if i < total - 1:  # Don't delay after the last sentence
            time.sleep(0.5)
    
    return themes

def fix_truncated_json(json_str):
    """Attempt to fix truncated JSON by balancing brackets."""
    # Count opening and closing braces/brackets
    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    open_brackets = json_str.count('[')
    close_brackets = json_str.count(']')
    
    # Add missing closing braces/brackets if needed
    if open_braces > close_braces:
        json_str += '}' * (open_braces - close_braces)
    if open_brackets > close_brackets:
        json_str += ']' * (open_brackets - close_brackets)
    
    # Handle truncated string values by trying to find unterminated quotes
    lines = json_str.split('\n')
    fixed_lines = []
    
    for line in lines:
        if line.count('"') % 2 == 1:  # Odd number of quotes indicates unterminated string
            line += '"'  # Add closing quote
        fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)

def plot_thematic_distribution(themes):
    """Plot the distribution of themes using seaborn style."""
    # Ensure all 6 themes are included even if not in the response
    all_theme_names = [
        "Opportunities for Practice and Reflection",
        "Effective Immediate Feedback",
        "Technical Issues and Frustrations",
        "Enhanced Clinical Reasoning and Diagnostic Skills",
        "Utility in Practicing Clinical Write-Ups",
        "Limitations in Simulating Real Interactions"
    ]
    
    # Create counts list, handling missing themes
    data = []
    for theme in all_theme_names:
        if theme in themes:
            # Handle case sensitivity in keys
            if 'Count' in themes[theme]:
                count = themes[theme]['Count']
            elif 'count' in themes[theme]:
                count = themes[theme]['count']
            else:
                # If count isn't available, try to count the feedback items
                if 'feedback' in themes[theme]:
                    count = len(themes[theme]['feedback'])
                else:
                    count = 0
        else:
            # Theme is missing from results
            count = 0
        
        data.append({"Theme": theme, "Count": count})
    
    # Convert to pandas DataFrame
    df = pd.DataFrame(data)
    
    # Sort by count in descending order
    df = df.sort_values("Count", ascending=False)
    
    # Set up the plot style and font sizes
    sns.set_style("whitegrid")
    plt.rcParams.update({
        'font.size': 14,
        'axes.labelsize': 16,
        'axes.titlesize': 18,
        'xtick.labelsize': 14,
        'ytick.labelsize': 14
    })
    
    # Create larger figure for better readability
    plt.figure(figsize=(14, 10))
    
    # Create the horizontal bar plot
    ax = sns.barplot(
        x="Count", 
        y="Theme", 
        data=df,
        palette=[
            "#7BAFD4",  # Light blue (Opportunities)
            "#E9A178",  # Light orange (Feedback)
            "#8CD1A8",  # Light green (Technical)
            "#E9A19F",  # Light red/pink (Clinical reasoning)
            "#D1BC8A",  # Light tan (Limitations)
            "#E8C3D7"   # Light pink (Utility)
        ]
    )
    
    # Set titles and labels with increased font sizes
    plt.title("Number of occurrences for each theme in student evaluations", fontsize=20, pad=20)
    plt.xlabel("Number of occurrences", fontsize=18)
    plt.ylabel("Concepts", fontsize=18)
    
    # Ensure x-axis ticks are integers only, showing every other tick
    max_count = df['Count'].max()
    plt.xlim(0, max_count + 1)  # Add some padding on the right
    
    # Create ticks at every integer, but only show labels for even numbers
    all_ticks = list(range(0, int(max_count) + 2))
    every_other_tick = all_ticks[::2]  # Get every other tick (0, 2, 4...)
    
    # Set the ticks and labels
    plt.xticks(all_ticks)  # Place ticks at every integer
    ax.set_xticklabels([str(tick) if tick in every_other_tick else '' for tick in all_ticks])
    
    # Add gridlines
    ax.xaxis.grid(True)
    ax.yaxis.grid(False)
    
    # Add a bit more padding around the plot
    plt.tight_layout(pad=2.0)
    
    # Save the figure with high resolution
    plt.savefig('thematic_analysis_plot.png', dpi=300, bbox_inches='tight')
    
    # Show the plot
    plt.show()

def main(pdf_path):
    # Check for OpenAI API key
    if not openai.api_key:
        print("Please set your OpenAI API key.")
        sys.exit(1)

    # Step 1: Extract text from PDF
    text = extract_text_from_pdf(pdf_path)

    # Step 2: Preprocess text
    sentences = preprocess_text(text)

    # Check if sentences are extracted
    if not sentences:
        print("No evaluations found in the PDF.")
        sys.exit(1)

    # Step 3: Process each sentence individually
    print(f"Classifying {len(sentences)} sentences using GPT-4...")
    themes = process_sentences(sentences)
    
    # Step 4: Save the JSON output to a file
    output_filename = "thematic_analysis_results.json"
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(themes, f, indent=2, ensure_ascii=False)
    print(f"\nSaved analysis results to {output_filename}")

    # Step 5: Plot the results (excluding the Uncategorized category from the plot)
    plot_themes = {k: v for k, v in themes.items() if k != "Uncategorized"}
    plot_thematic_distribution(plot_themes)
    print("\nAnalysis complete. Results plotted and saved to 'thematic_analysis_plot.png'")

if __name__ == '__main__':
    # Update the PDF path to your actual file location
    pdf_path = r'C:\Users\f006q7g\OneDrive - Dartmouth College\Research\MedEdResearch\AI in Education\OnDoc\data\OnDoc Survey evaluation.pdf'

    # Hardcode your OpenAI API key directly here
    openai.api_key = 'sk-xxxxxx'

    main(pdf_path)