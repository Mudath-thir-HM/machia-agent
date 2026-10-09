
---

{}

---

[![QuantFactory Banner](https://lh7-rt.googleusercontent.com/docsz/AD_4nXeiuCm7c8lEwEJuRey9kiVZsRn2W-b4pWlu3-X534V3YmVuVc2ZL-NXg2RkzSOOS2JXGHutDuyyNAUtdJI65jGTo8jT9Y99tMi4H4MqL44Uc5QKG77B0d6-JfIkZHFaUA71-RtjyYZWVIhqsNZcx8-OMaA?key=xt3VSDoCbmTY7o-cwwOFwQ)](https://hf.co/QuantFactory)


# aashish1904/N-ATLaS-GGUF
This is quantized version of [NCAIR1/N-ATLaS](https://huggingface.co/NCAIR1/N-ATLaS) created using llama.cpp

# Original Model Card

# N-ATLaS-LLM - Multilingual African Language Model

N-ATLaS-LLM is a fine-tuned multilingual language model based on Llama-3 8B, specifically designed to support African languages, including Hausa, Igbo, and Yoruba alongside English. This model is powered by **Awarri Technologies** an initiative of the **Federal Ministry of Communications, Innovation and Digital Economy**
as part of the Nigerian Languages AI Initiative to promote digital inclusion and preserve African linguistic heritage in the digital age.

## Model Overview

N-ATLaS-LLM is built on the Llama architecture and has been fine-tuned on over 400 million tokens of multilingual instruction data. The model demonstrates strong performance across multiple African languages while maintaining excellent English capabilities.

### Key Features
- **Multilingual Support**: Native support for English, Hausa, Igbo, and Yoruba
- **Cultural Relevance**: Trained on culturally relevant content from Nigerian sources
- **Instruction Following**: Fine-tuned for instruction-following tasks
- **Tool Integration**: Built-in support for tool integration capabilities

## Model Architecture

### Technical Specifications

| Parameter | Value |
|-----------|--------|
| **Model Type** | LlamaForCausalLM |
| **Base Model** | Llama-3 8B |
| **Hidden Size** | 4,096 |
| **Intermediate Size** | 14,336 |
| **Number of Layers** | 32 |
| **Attention Heads** | 32 |
| **Key-Value Heads** | 8 |
| **Head Dimension** | 128 |
| **Vocabulary Size** | 128,256 |
| **Max Position Embeddings** | 131,072 |
| **Context Length** | 8,092 tokens |



## Training Data

### Dataset Overview
N-ATLaS-LLM was trained on approximately **391,956,264 tokens** of quality multilingual instruction data.

| Language | SFT Samples |
|----------|-------------|
| English | ~318,000 |
| Hausa | ~200,000 |
| Igbo | ~200,000 |
| Yoruba | ~200,000 |

### Data Sources and Processing

#### 1. Data Collection Pipeline
- **Open-source datasets**: High-quality SFT datasets from Hugging Face and other repositories
- **Translation pipeline**: Robust translation using Google Translate and OpenAI GPT models
- **Synthetic data generation**: Culturally relevant content from Nigerian web sources (BBC Pidgin, Punch News)
- **Human-in-the-loop quality control**: Manual verification and cleaning of translated samples

#### 2. Data Quality Assurance
- **Multi-language categorization**: Topic/domain tagging and organization
- **Content filtering**: Removal of toxic, irrelevant, or hallucinated content
- **Translation verification**: Fixing translation errors and ensuring prompt-response alignment
- **Cultural relevance**: Focus on Nigerian and African cultural contexts

## Performance Evaluation

### Human Evaluation Results

Our model was evaluated by human annotators across multiple dimensions. Here are the results:

| Metric | English | Hausa | Yoruba | Igbo |
|--------|---------|--------|---------|------|
| **Evaluations** | 1,662 | 140 | 542 | 296 |
| **Average Score** | 4.21/5.0 | 3.98/5.0 | 2.69/5.0 | 3.87/5.0 |
| **Fluency** | 4.30/5.0 | 4.23/5.0 | 2.71/5.0 | 3.89/5.0 |
| **Coherence** | 4.22/5.0 | 3.70/5.0 | 3.23/5.0 | 3.80/5.0 |
| **Relevance** | 4.28/5.0 | 3.76/5.0 | 2.89/5.0 | 3.85/5.0 |
| **Accuracy** | 4.23/5.0 | 3.72/5.0 | 3.13/5.0 | 3.92/5.0 |
| **Bias/Fairness** | 3.18/5.0 | 1.11/5.0 | 2.23/5.0 | 4.01/5.0 |
| **Usefulness** | 4.09/5.0 | 5.00/5.0 | 4.03/5.0 | 3.84/5.0 |

### Key Performance Insights
- **English**: Excellent performance across all metrics (4.21/5.0 average)
- **Hausa**: Strong performance with exceptional usefulness scores (5.0/5.0)
- **Igbo**: Solid performance across most metrics (3.87/5.0 average)
- **Yoruba**: Room for improvement, particularly in fluency and relevance

## Training Details

### Training Configuration
- **Optimizer**: AdamW 8-bit
- **Learning Rate**: 1e-5 with linear scheduler
- **Precision**: Mixed precision training (BF16/FP16 based on hardware)
- **Base Model**: Llama-3 8B parameters
- **Fine-tuning Method**: Supervised Fine-Tuning (SFT)

### Training Pipeline
1. **Data Preprocessing**: Multi-stage cleaning and filtering pipeline
2. **Supervised Fine-Tuning**: Instruction-following training on multilingual datasets
3. **Quality Validation**: Human evaluation across multiple languages and metrics

## 💻 Usage

### Installation
```bash
pip install transformers torch
```

### Basic Usage
```python
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

# Load model and tokenizer
model_name = "NCAIR1/N-ATLaS"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16,
    device_map="auto"
)

def format_text_for_inference(messages):
    
    current_date = datetime.now().strftime('%d %b %Y')
    text = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=False,
        date_string=current_date
    )
    
    return text


# Example usage
q_chat = [
        {'role':'system','content':'you are a large language model trained by Awarri AI technologies. You are a friendly assistant and you are here to help.'},
        {'role': 'user', 'content': "menene ake nufi da gwagwarmaya"}
    ]

text = format_text_for_inference(q_chat)

input_tokens = tokenizer(text,return_tensors='pt',add_special_tokens=False).to('cuda')
outputs = model.generate(
    **input_tokens,
    max_new_tokens = 1000,
    use_cache=True,
    repetition_penalty=1.12,
    temperature = 0.1
    )

text = tokenizer.batch_decode(outputs)[0]
print(text)

```
### Inference Output

```python
<|begin_of_text|><|start_header_id|>system<|end_header_id|>

Cutting Knowledge Date: December 2023
Today Date: 11 Jun 2025

your name is AwaGPT, you are a large language model trained by Awarri AI technologies. You are a friendly assistant and you are here to help.<|eot_id|><|start_header_id|>user<|end_header_id|>

menene ake nufi da gwagwarmaya<|eot_id|><|start_header_id|>assistant<|end_header_id|>

A cikin mahallin ilimi, "gwagwarmaya" na nufin tsarin koyon halaye ko kwarewa ta hanyar maimaitawa, aiki, da kuma fuskantar kalubale. Yana jaddada rawar da kokari mai yawa ke takawa wajen samun nasara da ci gaba. Gwagwarmayar ba kawai game da samun sakamako ba ne amma har ma game da abubuwan da aka koya a lokacin aikin, wanda ke taimakawa wajen inganta kwarewa da tabbatar da canje-canjen da aka samu.

Ga karin bayani kan ra'ayoyin da suka shafi gwagwarmaya:

1. **Koyo Ta Hanyar Kwarewa**: Yana mai da hankali kan muhimmancin shiga cikin yanayi na zahiri don samun ilimi da fasaha. Maimakon kawai karantawa ko sauraron darasi, gwagwarmaya yana haɗa da aiwatar da ayyuka da warware matsaloli, wanda ke haifar da zurfin fahimta.

2. **Matsakaicin Kalubale**: Wannan hanya yawanci tana haɗa da fara da burin da ya wuce iyawarka na yanzu (matsakaici) sannan ka yi aiki don cimma wannan burin. Ta wannan hanyar, kana koyon iyakokin ka da wuraren da za a inganta, wanda ke haifar da ci gaban mutum da kuma ƙarfafawa.

3. **Dorewa**: Ingantaccen koyo ta hanyar gwagwarmaya na iya zama dindindin idan an sake fuskantar kalubalen a tsawon lokaci. Ba kamar koyo na ɗan lokaci ba, inda ilimin zai iya zama ajiye ba tare da aiki ba, gwagwarmaya tana taimakawa wajen riƙe ilimi ta hanyar ci gaba da bukatar amfani da shi.

4. **Halin Juriya**: Gwagwarmaya yawanci tana buƙatar jure gazawa da rashin nasara. Ta hanyar fuskantar wahala akai-akai, mutane suna haɓaka juriya da ƙudurin warware matsaloli, waɗannan halaye masu mahimmanci ga nasara a dogon lokaci.

5. **Haɓaka Kai**: Gwagwarmaya ana amfani da ita sosai a cikin horon kai don taimakawa mutane su shawo kan tsoro, gina kwarin gwiwa, da haɓaka ikon sarrafa kansu. Yana haɓaka tunani mai kyau da kuma motsa mutane su tura iyakokinsu.

6. **Amfani a Fannonin Daban-daban**: Ana amfani da manufar gwagwarmaya ba kawai a fannin ilimi ba; ana amfani da ita a fannonin kamar wasanni, horon sana'a, da ci gaban mutum. Misali, dan wasa na iya amfani da gwagwarmaya don inganta dabaru ko kwarewa, yayin da mai sana'a zai iya amfani da ita don koyo sabbin fasahohi ko dabaru.

A taƙaice, gwagwarmaya wata hanya ce mai tasiri ta koyo da ci gaba wacce ke jaddada mahimmancin aiki, juriya, da ci gaba mai dorewa. Yana taimakawa mutane su sami ilimi da kwarewa da za su iya amfani da su a rayuwa ta zahiri.<|eot_id|>
```

### Supported Languages
- **English**: Full support with high performance
- **Hausa**: Native support with cultural context
- **Igbo**: Native support with cultural context  
- **Yoruba**: Native support with ongoing improvements

## Use Cases

This model is designed for:
- **Multilingual Chatbots**: Deploy conversational AI in African languages
- **Content Translation**: Translate between English and African languages
- **Educational Tools**: Create learning materials in local languages
- **Cultural Preservation**: Document and preserve African linguistic heritage
- **Government Services**: Provide AI-powered services in local languages
- **Digital Inclusion**: Bridge the language gap in technology access
- **Research Applications**: Support research in Nigerian and African language technologies

## Limitations


- **Bias Concerns**: Some bias issues identified.
- **Context Length**: Limited to 8,092 tokens for optimal performance
- **Domain Coverage**: Primarily trained on instruction-following tasks

## Future Work

- **RLHF Training**: Implementation of reinforcement learning with human feedback
- **Performance Improvements**: Targeted improvements across all languages.
- **Bias Mitigation**: Enhanced bias detection and mitigation strategies
- **Extended Context**: Support for longer context lengths
- **Additional Datasets**: More SFT datasets for improved and better performance across the local languages.
- **Additional Languages**: Expansion to more African languages

## Ethical Considerations

- This model was developed as part of a Federal Government initiative to promote digital inclusion
- Training data collection followed ethical guidelines for data usage and cultural sensitivity
- The model aims to preserve and promote African languages in digital spaces
- Efforts were made to ensure cultural relevance and accuracy across all supported languages

## Contact & Support
- **Initiative Of**: Federal Ministry of Communications, Innovations, and Digital Economy
- **Powered By**: Awarri Technologies
- **Project**: Nigerian Languages AI Initiative (Federal Government Collaboration)
- **Version**: 1.0 (September 2025)

For issues, questions, or collaboration opportunities, please refer to the model repository discussions or contact Awarri Technologies.

## Acknowledgments

This work was made possible through:
- AWARRI Technologies
- National Information Technology Development Agency (NITDA)
- The Federal Ministry of Communications, Innovation and Digital Economy
- National Center for Artificial Intelligence and Robotics
- Data contributors from across Nigeria's 6 geopolitical zones via the Langeasy platform
- The broader Nigerian language technology research community

## 📄 Citation

```bibtex
@misc{awagptv1_2025,
  title={N-ATLaS-LLM: A Multilingual African Language Model},
  author={Awarri Technologies and National Information Technology and Development Agency},
  year={2025},
  publisher={Hugging Face},
  note={Fine-tuned Llama-3 8B model for African languages developed in collaboration with the Federal Government of Nigeria}
}
```
## 📜 License

# Terms of Use for N-ATLaS  
*(Nigeria – Automatic Transcription and Language Systems)*  

**Effective Date:** September 2025  
**Version:** 1.0  

---

## 1. Introduction & Scope  
Awarri Technologies, in partnership with the Federal Government of Nigeria, hereby releases **N-ATLaS** (Nigeria – Automatic Transcription and Language Systems), consisting of four Automatic Speech Recognition (ASR) models and one Text Large Language Model (LLM) for Nigerian languages (Yoruba, Hausa, Igbo, and Nigerian-accented English).  

N-ATLaS is released under an **Open-Source Research and Innovation License** inspired by permissive licenses such as Apache 2.0 and MIT, but with additional restrictions tailored for responsible use in Nigeria and globally.  

The models are intended to support:  
- Research and academic study  
- Education and capacity development  
- Civic technology and accessibility initiatives  
- Innovation, cultural preservation, and community projects  

⚠️ N-ATLaS is **not** an enterprise-grade or commercial system. Commercial or large-scale enterprise use requires a separate licensing agreement (see Section 3).  

---

## 2. License Grant  
Subject to compliance with these Terms, users are hereby granted a worldwide, royalty-free, non-exclusive, non-transferable license to:  
- Download, use, and run N-ATLaS for permitted purposes  
- Modify, adapt, and create derivative works of N-ATLaS  
- Redistribute N-ATLaS and derivative works under these same Terms  

**Conditions:**  
1. Attribution must be given to:  
   > “Awarri Technologies and the Federal Ministry of Communications, Innovation and Digital Economy
.”  

2. Derivative works must be released under the same license, ensuring consistency and traceability.  
3. If N-ATLaS or its derivatives are renamed, they must carry the suffix: **“Powered by Awarri.”**  

---

## 3. User License Cap (1000 Users)  
Use of N-ATLaS is limited to organizations, institutions, or projects with no more than **1000 active end-users**.  

- An *active end-user* is defined as an individual who directly interacts with N-ATLaS outputs (e.g., via an app, website, or integrated service) within a rolling 30-day period.  
- Organizations exceeding the 1000-user cap must obtain a **commercial license** directly from Awarri Technologies in partnership with the Federal Ministry of Communications, Innovation, and Digital Economy.  

---

## 4. Acceptable Use  

### ✅ Permitted Use Cases include (but are not limited to):  
- Academic and non-profit research  
- Accessibility for persons with disabilities  
- Language and cultural preservation projects  
- Civic technology and public benefit applications  
- Education, training, and community innovation  

### ❌ Prohibited Use Cases include (but are not limited to):  
- Surveillance or unlawful monitoring  
- Discriminatory profiling or exclusionary practices  
- Disinformation, impersonation, or synthetic fraud  
- Military, intelligence, or weaponized deployment  
- Exploitative, harmful, or unlawful applications  

---

## 5. Limitations & Disclaimer  
- N-ATLaS is released **“as-is”**, without warranties of any kind, express or implied.  

**Known limitations include:**  
- Dialectal and accent bias  
- Reduced accuracy with children’s speech  
- Limited handling of code-switching  
- Degraded performance in noisy environments  

Neither Awarri Technologies nor the Federal Ministry of Communications, Innovation and Digital Economy
 shall be liable for damages arising from the use of N-ATLaS.  

---

## 6. Ethical & Cultural Considerations  
Users must:  
- Respect Nigeria’s cultural and linguistic diversity  
- Ensure transparent reporting of accuracy, bias, and limitations  
- Uphold human rights and privacy standards in all deployments  

---

## 7. Data & Privacy  
- All training data used in N-ATLaS was either publicly available or government-approved for use.  
- Users are strictly prohibited from using N-ATLaS for unauthorized personal data scraping, collection, or profiling.  

---

## 8. Governance & Updates  
- Governance and oversight will be led by the **Federal Ministry of Communications, Innovation, and Digital Economy**, in collaboration with the **National Centre for Artificial Intelligence and Robotics (NCAIR)**.  
- **Awarri Technologies** shall act as the technical maintainer and custodian of N-ATLaS.  
- Updates, improvements, and community contributions will be published periodically.  
- Users must comply with the specific Terms attached to each version release.  

---

## 9. Legal & Jurisdiction  
- These Terms are governed by the laws of the **Federal Republic of Nigeria**.  
- In the event of a dispute, parties agree to seek resolution first through **mediation under the auspices of the Federal Ministry of Justice** before pursuing litigation in Nigerian courts.  

---

## 10. Termination  
The Federal Government of Nigeria and Awarri Technologies reserve the right to revoke, suspend, or terminate usage rights if these Terms are violated.  

Termination may apply to individual users, institutions, or organizations found in breach.  

---

## 11. Contact & Attribution  

For licensing, inquiries, and commercial partnerships regarding N-ATLaS, contact:  

**Awarri Technologies**  
- Email: [datasupport@awarri.com](mailto:datasupport@awarri.com)  
- Website: [awarri.com](https://awarri.com)  

**Federal Ministry of Communications, Innovation, and Digital Economy**  
- Email: ncair@nitda.gov.ng 
- Website: ncair.nitda.gov.ng

**Required attribution in all public use:**  
> “N-ATLaS is an initiative of the Federal Ministry of Communications, Innovation and Digital Economy, and powered by Awarri Technologies.”  

If renamed, the model must carry the suffix:  
> **“Powered by Awarri.”**  




*N-ATLaS-LLM is part of Awarri Technologies' mission, initiated by the The Federal Ministry of Communications, Innovation and Digital Economy
, to make AI accessible to African language speakers and preserve linguistic diversity in the digital age.*

