# Responsible Use Policy

This repository provides an educational web-scraping tool. The maintainers require that anyone using this tool follows these rules:

1. **Permission First**  
   Only run this tool against systems you own or systems where you have **explicit, written permission** to perform scraping or reconnaissance. Examples of allowed environments:
   - Your own servers.
   - Official lab environments that explicitly permit these activities (e.g., TryHackMe/Hack The Box labs when allowed).
   - Servers where the owner granted permission.

2. **Respect Robots.txt (Default)**  
   The tool respects `robots.txt` by default. If you disable that behavior, do so only in permitted lab environments and document why.

3. **Rate Limiting**  
   Use conservative rate limits and set a delay between requests to avoid service disruption.

4. **No Exploitation**  
   This tool is **not** to be used for vulnerability scanning, fuzzing, automated exploitation, or data exfiltration. It only collects publicly visible metadata (titles, forms structure, headers, etc.).

5. **Data Handling**  
   Do not collect, store, or share personal data or credentials you do not own or are not authorized to handle.

6. **Report Misuse**  
   If you see this project being used to facilitate wrongdoing, please contact the maintainers or platform administrators.

By using this repository you agree to follow this policy. The maintainers reserve the right to remove or refuse contributions that violate these guidelines.
