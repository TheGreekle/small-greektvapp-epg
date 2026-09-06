# Small-greektv.app-EPG 🇬🇷 

#EXTM3U x-tvg-url="https://thegreekle.github.io/small-greektvapp-epg/small-epg.xml"

• epg xml file is smaller than 0,5 MB 

• automatically for greek iptv lists or apps like GoTV 

• 30 Channels 
• m3u tvg-id's: 
• ert1 • ert2 • ert3 
• mega • ant1 • alpha 
• skai • open • star 
• starint • mtv 
• tv100 • onetv 
• vouli • ertworld 
• ertnews • meganews 
• pronews • action24 
• ertsports • ertsports2 
• riksat • omega • ant1cy 
• sigma •  berginacy 
• rikhd • rik1 • rik2 
• Naftemporikitv • 

               
❕———__________________________________———❕

• Android users can also use/install the app on/from the website "https://greektv.app" 📺 

• for more information visit: "https://github.com/tvappshq/epg-greece-cyprus" and "https://ko-fi.com/greektvapp" ☕️ 

❕———__________________________________———❕


• My Construction: 

small-greektvapp-epg/

│

├── epg_filter.py

│

(├── small-epg.xml => in GitHub Pages: "https://thegreekle.github.io/small-greektvapp-epg/small-epg.xml")

│

├── .github/

│   └── workflows/

│       └── epg.yml

│

└── ssiptv-greek-epg/

    │
    
    ├── wrangler.jsonc
    
    │
    
    └── public/
    
        ├── _headers
        
        └── ssiptv-epg.xml ("https://raw.githubusercontent.com/TheGreekle/small-greektvapp-epg/refs/heads/main/ssiptv-greek-epg/public/ssiptv-epg.xml")
        

 • Build:

                  GitHub Actions
                  
                       │
                       
                       ▼
                       
                 EPG generating
                 
                       │
                       
              ┌────────┴────────┐
              
              ▼                 ▼
              
        GitHub Pages       Cloudflare
       
       small-epg.xml      ssiptv-epg.xml
      
              │                 │
              
              ▼                 ▼
              
         IPTV Player          SS IPTV
