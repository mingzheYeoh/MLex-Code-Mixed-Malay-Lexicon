"""
New Unified WSD Module
Allows users to input multiple sentences and analyze a target word across all contexts
"""
import streamlit as st
import json
import pandas as pd
from datetime import datetime


def render_unified_wsd_page(neo4j_conn, ai_service):
    """Unified WSD Page - Analyze one word across multiple sentences"""
    st.title("🎯 WSD (Word Sense Disambiguation)")

    if not ai_service:
        st.error("⚠️ No AI service available!")
        st.info("Please ensure Ollama is running or set GEMINI_API_KEY")
        return

    st.markdown("""
    ### 📖 How to use:
    1. Enter **at least 2 sentences** (one per line)
    2. Specify the **target word** to analyze
    3. Click **Analyze** to see how the word's meaning differs across sentences
    4. Download or copy results in JSON format
    """)

    st.markdown("---")

    # Input Section
    st.markdown("### 📝 Input")

    col1, col2 = st.columns([3, 1])

    with col1:
        sentences_input = st.text_area(
            "Enter sentences (one per line, minimum 2)",
            placeholder="Example:\nSaya makan nasi goreng\nBateri makan kuasa\nKanak-kanak main bola\nDia main piano",
            height=150,
            help="Enter at least 2 sentences, each containing the target word"
        )

    with col2:
        target_word = st.text_input(
            "Target word",
            placeholder="Example: makan",
            help="The word you want to analyze across different contexts"
        )

    st.markdown("---")

    # Analysis Button
    if st.button("🚀 Analyze", type="primary", width="stretch"):
        # Validation
        if not sentences_input or not target_word:
            st.error("❌ Please enter both sentences and target word")
            return

        # Parse sentences
        sentences = [s.strip() for s in sentences_input.split('\n') if s.strip()]

        if len(sentences) < 2:
            st.error("❌ Please enter at least 2 sentences")
            return

        # Check if target word exists in all sentences
        sentences_with_word = []
        sentences_without_word = []

        for sent in sentences:
            if target_word.lower() in sent.lower():
                sentences_with_word.append(sent)
            else:
                sentences_without_word.append(sent)

        if sentences_without_word:
            st.warning(f"⚠️ The following sentences do not contain '{target_word}' and will be skipped:")
            for sent in sentences_without_word:
                st.caption(f"  • {sent}")

        if len(sentences_with_word) < 2:
            st.error(f"❌ At least 2 sentences must contain the word '{target_word}'")
            return

        # Get candidate senses from database
        with st.spinner(f"Retrieving candidate meanings for '{target_word}'..."):
            senses = neo4j_conn.get_all_senses_for_word(target_word)

            if not senses:
                st.error(f"❌ Word '{target_word}' not found in database")
                st.info("💡 Available test words: makan, main, buah, kena, buat")
                return

            if len(senses) == 1:
                st.info(f"ℹ️ Word '{target_word}' has only 1 meaning in the database")
                st.write(f"**Meaning:** {senses[0].definition}")
                return

        # Perform WSD analysis for each sentence
        st.markdown("### 📊 Analysis Results")

        progress_bar = st.progress(0)
        status_text = st.empty()

        results_list = []

        for idx, sentence in enumerate(sentences_with_word):
            status_text.text(f"Analyzing sentence {idx+1}/{len(sentences_with_word)}...")

            # Call AI WSD
            wsd_results = ai_service.disambiguate(
                word=target_word,
                context=sentence,
                candidate_senses=tuple(senses)
            )

            top_result = wsd_results[0]

            # Store result
            result_entry = {
                'sentence_id': idx + 1,
                'sentence': sentence,
                'target_word': target_word,
                'predicted_sense_id': top_result['sense_id'],
                'predicted_definition': top_result['definition'],
                'confidence': top_result['confidence'],
                'reasoning': top_result['reasoning'],
                'all_candidates': [
                    {
                        'sense_id': r['sense_id'],
                        'definition': r['definition'],
                        'confidence': r['confidence']
                    } for r in wsd_results
                ]
            }

            results_list.append(result_entry)
            progress_bar.progress((idx + 1) / len(sentences_with_word))

        status_text.text("✅ Analysis completed!")
        progress_bar.empty()
        status_text.empty()

        # Display results
        st.markdown("---")
        display_wsd_results(results_list, target_word)

        # JSON output section
        st.markdown("---")
        st.markdown("### 💾 Export Results")

        # Create comprehensive JSON output
        json_output = {
            'analysis_metadata': {
                'target_word': target_word,
                'total_sentences': len(sentences_with_word),
                'timestamp': datetime.now().isoformat(),
                'ai_service': ai_service.__class__.__name__
            },
            'results': results_list
        }

        json_str = json.dumps(json_output, indent=2, ensure_ascii=False)

        col1, col2 = st.columns(2)

        with col1:
            st.download_button(
                label="📥 Download JSON",
                data=json_str,
                file_name=f"wsd_{target_word}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )

        with col2:
            if st.button("📋 Copy JSON to Clipboard"):
                st.code(json_str, language='json')
                st.success("✅ JSON displayed above - you can copy it manually")

        # Show JSON preview
        with st.expander("🔍 Preview JSON Output"):
            st.json(json_output)


def display_wsd_results(results_list, target_word):
    """Display WSD results in a user-friendly format"""

    st.markdown(f"### 🎯 Word: **{target_word}**")
    st.markdown(f"📊 Analyzed **{len(results_list)}** sentences")

    # Summary statistics
    avg_confidence = sum(r['confidence'] for r in results_list) / len(results_list)
    unique_senses = len(set(r['predicted_sense_id'] for r in results_list))

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Sentences", len(results_list))
    with col2:
        st.metric("Unique Meanings", unique_senses)
    with col3:
        st.metric("Avg Confidence", f"{avg_confidence:.1f}%")

    st.markdown("---")

    # Display each result
    for result in results_list:
        confidence = result['confidence']

        # Confidence badge
        if confidence > 70:
            emoji = "🟢"
            badge_color = "green"
        elif confidence > 40:
            emoji = "🟡"
            badge_color = "orange"
        else:
            emoji = "🔴"
            badge_color = "red"

        with st.expander(
            f"{emoji} Sentence {result['sentence_id']}: {result['sentence'][:60]}... ({confidence:.1f}%)",
            expanded=True
        ):
            # Sentence
            st.markdown(f"**📝 Sentence:**")
            st.info(result['sentence'])

            # Predicted meaning
            st.markdown(f"**🎯 Predicted Meaning:**")
            st.success(result['predicted_definition'])

            # Confidence bar
            st.markdown(f"**📊 Confidence:** {confidence:.1f}%")
            st.progress(confidence / 100.0)

            # Reasoning
            st.markdown(f"**💭 AI Reasoning:**")
            st.caption(result['reasoning'])

            # All candidates
            with st.expander("📋 All Candidate Meanings"):
                for idx, candidate in enumerate(result['all_candidates'], 1):
                    st.markdown(f"**{idx}.** {candidate['definition']}")
                    st.caption(f"   Confidence: {candidate['confidence']:.1f}%")
                    st.progress(candidate['confidence'] / 100.0)
                    st.markdown("")

    # Summary table
    st.markdown("---")
    st.markdown("### 📈 Summary Table")

    summary_data = []
    for r in results_list:
        summary_data.append({
            'ID': r['sentence_id'],
            'Sentence': r['sentence'][:50] + '...' if len(r['sentence']) > 50 else r['sentence'],
            'Predicted Meaning': r['predicted_definition'][:60] + '...' if len(r['predicted_definition']) > 60 else r['predicted_definition'],
            'Confidence': f"{r['confidence']:.1f}%"
        })

    df = pd.DataFrame(summary_data)
    st.dataframe(df, width="stretch", hide_index=True)
