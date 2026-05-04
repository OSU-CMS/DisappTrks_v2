# Instructions to run on swan
It's conveinient to run jupyter notebooks using swan. The swan website can be accessed at [](swan.cern.ch). This will give you access to all your files that are stored on your cernbox. You are also able to access files using xrootd, however, this takes some setting up. In order to get access to xrootd you will need to follow these steps: 
1. Create a .globus directory in your home directory using the terminal from swan. 
2. Copy over a valid grid certificate into that directory with swan 
3. Follow the instructions to setup your grid certificate from this link [](https://twiki.cern.ch/twiki/bin/view/CMSPublic/WorkBookStartingGrid#BasicGrid)
4. Run the voms-proxy-init command using the swan terminal

