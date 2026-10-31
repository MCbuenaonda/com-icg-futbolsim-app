"""
Nombres VEROSÍMILES (comunes en cada país, NO de personas conocidas) para los personajes ficticios: dueños y comentaristas de las
televisoras, dueños de las marcas y directores y periodistas de los medios. Antes se armaban mezclando nombres y apellidos de los
jugadores del sistema y se veían repetidos. Los usa renombrar_personajes.py. Solo nombres masculinos: los avatares son de hombre.

CULTURA_POR_ISO elige la lista por el país (los que no están caen en 'en'). APODOS: algunos comentaristas y periodistas se presentan
con apodo, como pasa en la vida real («José "El Profe" Hernández»).
"""

CULTURAS = {
    "es": ("José Juan Carlos Luis Miguel Jorge Pedro Manuel Francisco Javier Antonio Fernando Ricardo Roberto Eduardo Raúl Sergio Andrés "
           "Alberto Héctor Rafael Gustavo Óscar Rubén Hugo Ernesto Alfredo Mario Enrique Daniel Alejandro Martín Diego Pablo Gerardo Arturo Ramón Felipe",
           "García Martínez López Hernández González Pérez Rodríguez Sánchez Ramírez Torres Flores Rivera Gómez Díaz Cruz Morales Reyes Gutiérrez "
           "Ortiz Ruiz Jiménez Mendoza Castillo Romero Álvarez Vargas Herrera Medina Aguilar Vega Castro Ramos Guzmán Navarro Salazar Domínguez "
           "Cabrera Fuentes Ríos Pacheco Campos Rosales Sandoval Valdez Mejía Figueroa Ochoa Ibarra Cordero Bustamante Peralta Escobar Villalobos"),
    "pt": ("João José Antônio Carlos Paulo Pedro Luiz Marcos Ricardo Fernando Rodrigo Rafael Gustavo André Eduardo Sérgio Roberto Marcelo Fábio "
           "Leonardo Márcio Renato Alexandre Tiago Bruno Diogo Rui Nuno Hélio Vítor Jorge Mauro",
           "Silva Santos Oliveira Souza Rodrigues Ferreira Alves Pereira Lima Gomes Costa Ribeiro Martins Carvalho Almeida Lopes Soares Fernandes "
           "Vieira Barbosa Rocha Dias Nascimento Andrade Moreira Nunes Marques Machado Mendes Freitas Cardoso Ramos Gonçalves Teixeira Correia "
           "Pinto Moura Cavalcanti Monteiro Barros Tavares Peixoto Fonseca Azevedo"),
    "en": ("James John Robert Michael William David Richard Thomas Mark Paul Steven Andrew Kevin Brian Gary Peter Stephen Simon Martin Neil "
           "Graham Ian Colin Alan Keith Tony Chris Matt Dan Jim Ben Tom Craig Scott Ryan Jack",
           "Smith Jones Taylor Brown Williams Wilson Johnson Davies Robinson Wright Thompson Evans Walker White Roberts Green Hall Wood Jackson "
           "Clarke Harris Clark Lewis Turner Hill Cooper Ward Morris King Baker Harrison Morgan Parker Bennett Hughes Collins Edwards Stewart "
           "Murphy Kelly Fletcher Barnes Mitchell Chapman Grant Henderson"),
    "caribe": ("Andre Kevin Marlon Dwayne Ricardo Damion Garfield Wayne Courtney Delroy Winston Trevor Junior Shane Kirk Lennox Desmond Clive Earl "
               "Rohan Kemar Jermaine Omar Leroy Nigel Sheldon",
               "Williams Brown Campbell Thomas Edwards Charles Joseph James Francis Richards Henry Gordon Grant Bailey Morgan Simpson Lewis Phillip "
               "Baptiste Alexander Ramsaroop Mohammed Hosein Persaud Clarke Mitchell Roberts Douglas Benjamin Daniel Samuel Felix Augustine"),
    "fr": ("Jean Pierre Philippe Michel Alain Patrick Nicolas Christophe Laurent Stéphane Thierry Olivier Éric Frédéric Pascal Sébastien Julien "
           "Vincent Bruno Didier Gilles Jérôme François Bernard Marc Guillaume Antoine Hervé Yves Luc",
           "Martin Bernard Dubois Thomas Robert Richard Petit Durand Leroy Moreau Simon Laurent Lefebvre Michel Garcia David Bertrand Roux Vincent "
           "Fournier Morel Girard André Mercier Dupont Lambert Bonnet François Martinez Legrand Garnier Faure Rousseau Blanc Guerin Muller Henry "
           "Roussel Nicolas Perrin Morin Mathieu Clement Gauthier Dumont Lopez Fontaine Chevalier"),
    "af_fr": ("Moussa Ibrahim Mamadou Abdoulaye Ousmane Seydou Boubacar Amadou Issa Souleymane Cheick Bakary Lamine Adama Yacouba Aliou "
              "Jean-Pierre Serge Patrice Thierry Hervé Armand Fabrice Arsène Didier Romuald Bertrand Rodrigue Saturnin Ghislain",
              "Traoré Diallo Koné Coulibaly Camara Keita Touré Diarra Sangaré Ouédraogo Sawadogo Kaboré Ndiaye Diop Fall Sow Ba Gueye Mbaye "
              "Mensah Kouassi Kouamé Yao Konan Bamba Fofana Cissé Sylla Kanté Bah Barry Nkoulou Mbarga Ndongo Essomba Mvondo Tchakounté Kamga "
              "Ngoma Mabiala Moukoko Rakotomalala Randrianasolo Kabila Ilunga Mbuyi Tshibangu"),
    "af_oeste": ("Kwame Kofi Kojo Yaw Kwabena Emmanuel Samuel Daniel Joseph Michael Chinedu Emeka Obinna Chukwuemeka Tunde Femi Segun Yemi "
                 "Babatunde Olumide Ibrahim Musa Sani Abubakar Momodou Lamin Ebrima Foday Alhaji Mohamed",
                 "Mensah Asante Boateng Owusu Osei Agyemang Appiah Amoah Darko Addo Okafor Okonkwo Eze Nwosu Adeyemi Adebayo Olawale Ogunleye "
                 "Bello Abdullahi Yusuf Ibrahim Danjuma Jallow Ceesay Touray Sesay Kamara Bangura Conteh Koroma Johnson Tarr Kollie Doe Kpoto"),
    "af_este": ("John Peter Joseph James Daniel David Samuel Patrick Charles Moses Isaac Brian Dennis Godfrey Collins Wilson Kennedy Eric "
                "Jean-Claude Innocent Emmanuel Vincent Felix Hassan Juma Bakari Omari Abdallah",
                "Otieno Ochieng Odhiambo Kamau Mwangi Njoroge Kiprono Kipchoge Mutua Wanjala Okello Ssempijja Mukasa Kato Musoke Nakato Mwakyusa "
                "Massawe Mushi Mrisho Kimaro Habimana Niyonzima Uwimana Nkurunziza Hakizimana Ndayishimiye Deng Garang Lado Malual Akol"),
    "cuerno": ("Abebe Dawit Tesfaye Yohannes Solomon Bereket Haile Mulugeta Getachew Kebede Tewodros Amanuel Mekonnen Samuel Daniel Yonas "
               "Abdi Mohamed Ahmed Hassan Ali Omar Abdirahman Farah Ismail Yusuf Said Mahad",
               "Bekele Tadesse Haile Girma Alemu Tesfaye Wolde Mengistu Desta Kebede Gebremedhin Tekle Berhane Asfaw Abebe Mekonnen Negash "
               "Hussein Warsame Farah Jama Abdullahi Osman Elmi Hirsi Aden Dirie Gedi Nur"),
    "af_sur": ("Sipho Thabo Mandla Themba Bongani Lungile Sibusiso Tshepo Lebogang Kagiso Mpho Tumelo Neo Kabelo Tendai Tatenda Farai Blessing "
               "Chipo Mulenga Bwalya Chanda Kondwani Chimwemwe Pule Teboho Mothusi Oratile Johannes Petrus",
               "Dlamini Nkosi Ndlovu Khumalo Mokoena Mahlangu Sithole Zulu Mthembu Ngcobo Moyo Ncube Sibanda Mutasa Chikwanha Banda Phiri Mwale "
               "Tembo Zimba Chirwa Mbewe Kgosi Molefe Masilo Mosimane Seretse Lekhanya Mokhele Shikongo Nghipandulwa"),
    "arabe": ("Mohamed Ahmed Ali Omar Khaled Youssef Ibrahim Hassan Mahmoud Mostafa Tarek Sami Walid Karim Hani Ziad Fadi Nabil Adel Samir "
              "Abdullah Faisal Saud Sultan Nasser Majid Rashid Hamad Fahad Saleh",
              "Al-Hashimi Al-Mansouri Al-Qahtani Al-Shammari Al-Otaibi Al-Harbi Al-Ghamdi Al-Zahrani Al-Dosari Al-Mutairi Al-Kuwari Al-Marri "
              "Al-Khalifa Al-Balushi Al-Habsi Haddad Khoury Nasser Saleh Abdel-Rahman El-Sayed Farouk Mansour Hamdi Sabry Fathy Ezzat Hegazy "
              "Shehata Barakat Darwish Zaki Haddadin Tamimi Qasem Jaber Nassar Awad Shalabi"),
    "magreb": ("Mohamed Ahmed Youssef Karim Mehdi Amine Hicham Rachid Nabil Samir Mourad Khalid Said Abdelkader Djamel Farid Sofiane Yacine "
               "Hamza Tarik Adel Bilal Ilyes Walid Nordine Lotfi Riad Anis Mounir Othmane",
               "Benali Bouzid Belkacem Benaissa Haddad Mansouri Cherif Saidi Brahimi Rahmani Ziani Belhadj Hamdi Trabelsi Jaziri Ben Salah Gharbi "
               "Ben Youssef Chaabane El Amrani Bennani Alaoui Tazi Berrada Lahlou El Idrissi Benjelloun Ouali Kaddouri Ould Ahmed"),
    "de": ("Thomas Michael Andreas Stefan Christian Markus Frank Jürgen Klaus Peter Wolfgang Uwe Matthias Ralf Jörg Holger Dirk Sven Tobias "
           "Florian Sebastian Alexander Martin Rainer Bernd Helmut Torsten Lukas Jan Philipp",
           "Müller Schmidt Schneider Fischer Weber Meyer Wagner Becker Schulz Hoffmann Schäfer Koch Bauer Richter Klein Wolf Schröder Neumann "
           "Schwarz Zimmermann Braun Krüger Hofmann Hartmann Lange Schmitt Werner Krause Meier Lehmann Huber Gruber Steiner Moser Brunner "
           "Lang Winkler Berger Fuchs Keller Vogel Frank Roth Beck Lorenz Baumann"),
    "nl": ("Jan Pieter Kees Henk Johan Wim Gerard Erik Marco Dennis Sander Bas Joost Ruud Frank Jeroen Martijn Rob Hans Arjen Niels Thijs Bram "
           "Stefan Ronald Edwin Patrick Remco",
           "de Jong Jansen de Vries van den Berg van Dijk Bakker Janssen Visser Smit Meijer de Boer Mulder de Groot Bos Vos Peters Hendriks "
           "van Leeuwen Dekker Brouwer de Wit Dijkstra Smits de Graaf van der Meer van der Linden Kok Jacobs de Haan Vermeulen van den Heuvel "
           "Koster Willems Martens Kuiper"),
    "it": ("Marco Giuseppe Giovanni Francesco Antonio Alessandro Andrea Luca Roberto Stefano Paolo Massimo Fabio Davide Matteo Simone Claudio "
           "Maurizio Fabrizio Riccardo Lorenzo Gianluca Daniele Federico Enrico Sergio Carlo Pietro Vincenzo Mario",
           "Rossi Russo Ferrari Esposito Bianchi Romano Colombo Ricci Marino Greco Bruno Gallo Conti De Luca Mancini Costa Giordano Rizzo "
           "Lombardi Moretti Barbieri Fontana Santoro Mariani Rinaldi Caruso Ferrara Galli Martini Leone Longo Gentile Martinelli Vitale "
           "Lombardo Serra Coppola De Santis D'Angelo Marchetti Parisi Villa Conte Ferraro Fabbri"),
    "malta": ("Joseph John Mario Charles Paul Anthony Michael Carmel Raymond George Mark David Kevin Jean Clayton Ryan",
              "Borg Camilleri Vella Farrugia Zammit Galea Micallef Grech Attard Spiteri Azzopardi Mizzi Cassar Pace Gauci Agius Caruana Fenech"),
    "nordico": ("Lars Anders Erik Per Jan Magnus Henrik Johan Mikael Fredrik Nils Ole Bjørn Kjetil Stian Thomas Martin Jonas Kristian Rasmus "
                "Søren Jesper Mads Gunnar Sigurd Einar Jón Gudmundur Halldór Ragnar",
                "Hansen Johansen Olsen Larsen Andersen Pedersen Nilsen Kristiansen Jensen Karlsen Johansson Andersson Karlsson Nilsson Eriksson "
                "Larsson Olsson Persson Svensson Gustafsson Lindberg Lindqvist Berg Holm Dahl Lund Nielsen Christensen Rasmussen Jónsson "
                "Sigurdsson Gudmundsson Magnusson Petersen Joensen"),
    "fi": ("Matti Mikko Jari Juha Timo Kari Pekka Antti Markku Petri Jukka Tuomas Ville Janne Sami Heikki Teemu Lauri",
           "Korhonen Virtanen Mäkinen Nieminen Mäkelä Hämäläinen Laine Heikkinen Koskinen Järvinen Lehtonen Lehtinen Saarinen Salminen "
           "Heinonen Niemi Heikkilä Kinnunen Salonen Turunen"),
    "baltico": ("Andrus Jaan Tiit Rein Toomas Mart Indrek Jānis Andris Māris Edgars Gints Juris Tomas Mindaugas Darius Andrius Paulius Vytautas Giedrius",
                "Tamm Saar Sepp Mägi Kask Kukk Rebane Ilves Bērziņš Kalniņš Ozoliņš Jansons Liepiņš Krūmiņš Kazlauskas Jankauskas Petrauskas "
                "Stankevičius Vasiliauskas Žukauskas Butkus Paulauskas"),
    "eslavo": ("Aleksandr Dmitri Sergei Andrei Alexei Mikhail Ivan Nikolai Vladimir Oleg Igor Pavel Yuri Viktor Roman Denis Tomasz Piotr "
               "Krzysztof Marek Paweł Jakub Michał Petr Jiří Martin Tomáš Luka Marko Nikola Stefan Goran Dragan Milan Ivo Boris",
               "Ivanov Smirnov Kuznetsov Popov Volkov Sokolov Lebedev Kozlov Novikov Morozov Petrov Pavlov Kovalenko Bondarenko Shevchenko "
               "Tkachenko Kravchenko Nowak Kowalski Wiśniewski Wójcik Kamiński Lewandowski Zieliński Szymański Novák Svoboda Dvořák Černý "
               "Horvat Kovačević Babić Marić Jovanović Petrović Nikolić Marković Đorđević Ilić Stojanović Georgiev Dimitrov Ivanović Hodžić Begić"),
    "albanes": ("Arben Besnik Dritan Ilir Ermal Gentian Agron Fatmir Bujar Blerim Florian Shpëtim Artan Valon Driton Lulzim",
                "Hoxha Krasniqi Berisha Gashi Shala Morina Kelmendi Lika Shehu Basha Dervishi Kastrati Rama Bytyqi Mustafa Zeqiri"),
    "griego": ("Ioannis Georgios Konstantinos Dimitrios Nikolaos Christos Panagiotis Andreas Vasileios Stavros Michalis Kostas Petros Thanasis Spyros",
               "Papadopoulos Georgiou Nikolaou Konstantinou Ioannou Christodoulou Papageorgiou Vlachos Oikonomou Makris Antoniou Dimitriou Karagiannis Pappas Charalambous"),
    "rumano": ("Ion Mihai Andrei Cristian Florin Adrian Gabriel Bogdan Alexandru Ionuț Marius Daniel Vasile Sorin Radu",
               "Popescu Ionescu Popa Stan Dumitru Stoica Munteanu Marin Constantin Gheorghe Rusu Lungu Ciobanu Moldovan Ungureanu"),
    "hungaro": ("László Zoltán Attila Gábor Tamás Péter István Sándor József Ferenc Csaba Balázs Zsolt Norbert",
                "Nagy Kovács Tóth Szabó Horváth Varga Kiss Molnár Farkas Németh Balogh Papp Takács Juhász"),
    "turco": ("Mehmet Mustafa Ahmet Ali Hüseyin Hasan İbrahim Murat Emre Burak Serkan Volkan Kemal Selim Cem Onur Ozan Tolga Uğur Barış "
              "Elvin Rashad Farid Orkhan Tural Anar Elnur Ramil",
              "Yılmaz Kaya Demir Şahin Çelik Yıldız Yıldırım Öztürk Aydın Özdemir Arslan Doğan Kılıç Aslan Çetin Kara Koç Kurt Özkan Şimşek "
              "Polat Erdem Aliyev Mammadov Huseynov Hasanov Guliyev Ismayilov Rzayev Abbasov"),
    "caucaso": ("Giorgi David Levan Nika Irakli Zurab Davit Lasha Tamaz Gocha Aram Armen Vahe Tigran Hayk Karen Gor Artur",
                "Beridze Kapanadze Gelashvili Maisuradze Lomidze Tsiklauri Kvaratskhelia Japaridze Khutsishvili Chkheidze Hovhannisyan "
                "Harutyunyan Sargsyan Khachatryan Petrosyan Grigoryan Vardanyan Avetisyan Gasparyan Karapetyan"),
    "israel": ("David Yosef Moshe Avi Eyal Itzik Yossi Ronen Amir Oren Eran Gil Tal Omer Nir Shai Ido Lior",
               "Cohen Levi Mizrahi Peretz Biton Dahan Avraham Friedman Azulay Malka Katz Ohayon Amar Gabay Ben-David Shapira Rosen Golan"),
    "centroasia": ("Nurlan Yerlan Askar Bauyrzhan Daniyar Azamat Timur Rustam Farrukh Bekzod Jasur Sardor Aziz Shakhzod Bakhtiyar Murat Ruslan Dilshod",
                   "Nurlanov Akhmetov Seitkali Zhakupov Bekov Abenov Iskakov Toktarov Karimov Rashidov Yusupov Tursunov Nazarov Saidov Rakhimov "
                   "Kurbanov Sultanov Abdullaev Ergashev Mirzaev"),
    "persa": ("Ali Reza Mohammad Hossein Mehdi Amir Hamid Saeed Majid Behnam Farhad Kaveh Babak Dariush Ahmad Javad Mahmoud Navid Sohrab Farid",
              "Hosseini Mohammadi Rezaei Ahmadi Karimi Moradi Jafari Rahimi Hashemi Ebrahimi Sadeghi Ghasemi Rostami Kazemi Nazari Akbari "
              "Sharifi Habibi Ahmadzai Popal Durrani Sultani"),
    "sudasia": ("Rahul Amit Vikram Sanjay Arjun Rohit Anil Ravi Sunil Rajesh Prakash Suresh Ramesh Deepak Manoj Ashok Vijay Naveen Karan Ajay "
                "Tenzin Kinley Nimal Chaminda Kumar",
                "Sharma Verma Gupta Singh Kumar Patel Reddy Nair Iyer Menon Chatterjee Banerjee Das Bose Joshi Mehta Rao Pillai Shrestha Thapa "
                "Gurung Rai Perera Fernando Silva Jayasuriya Wickramasinghe Dorji Wangchuk"),
    "sudasia_m": ("Imran Faisal Usman Bilal Kamran Tariq Asif Shahid Rafiq Anwar Ahmed Ibrahim Mohammad Nadeem Waqar Shoaib Rashed Mahmud Hasan Ali",
                  "Khan Ahmed Hussain Qureshi Malik Chaudhry Butt Mirza Rahman Islam Hossain Chowdhury Siddiqui Sheikh Akhtar Iqbal Raza Haque Didi Manik"),
    "chino": ("Wei Jun Lei Hao Peng Tao Ming Qiang Jian Bo Gang Hui Yang Chen Zhiwei Jianguo Haoran Zihan Kai Yong",
              "Wang Li Zhang Liu Chen Yang Huang Zhao Wu Zhou Xu Sun Ma Zhu Hu Guo He Lin Luo Gao Liang Zheng Xie Tang Han Feng Deng Cao Peng Zeng"),
    "kr": ("Min-jun Seo-jun Ji-ho Hyun-woo Joon-ho Sung-min Dong-hyun Jae-won Tae-hoon Sang-woo Young-ho Kyung-soo Jin-woo Woo-jin Seung-hoon",
           "Kim Lee Park Choi Jung Kang Cho Yoon Jang Lim Han Oh Seo Shin Kwon Hwang Ahn Song Jeon Hong"),
    "jp": ("Hiroshi Takashi Kenji Satoshi Yuki Daisuke Takuya Kazuki Shota Naoki Ryota Kenta Tomohiro Masahiro Yusuke Akira Kenichi Shinji",
           "Sato Suzuki Takahashi Tanaka Watanabe Ito Yamamoto Nakamura Kobayashi Kato Yoshida Yamada Sasaki Yamaguchi Matsumoto Inoue Kimura "
           "Hayashi Shimizu Mori Ikeda Hashimoto Ishikawa Ogawa"),
    "mn": ("Bat-Erdene Ganbold Bold Enkhbayar Tsogt Munkh-Erdene Sukhbaatar Erdenebat Temuulen Batbayar",
           "Ganbaatar Dorj Bat Enkhtuya Tserendorj Altangerel Sukhbat Purevdorj Baatar Otgonbayar"),
    "indomalayo": ("Agus Budi Dedi Eko Hendra Rizky Bambang Joko Ahmad Muhammad Hafiz Faizal Azman Irfan Andi Yusuf Rudi Fauzi Haris Zulkifli",
                   "Santoso Wijaya Hidayat Saputra Setiawan Pratama Nugroho Kurniawan Abdullah Ismail Rahman Hamid Ibrahim Hasan Yusof Othman Halim Salleh"),
    "filipino": ("Jose Mark John Paolo Miguel Rafael Carlo Juan Antonio Ramon Ricardo Jerome Christian Angelo Joel",
                 "Reyes Santos Cruz Bautista Garcia Mendoza Ramos Aquino Villanueva Castillo Navarro Dela Cruz Fernandez Torres Lim Tan"),
    "tai": ("Somchai Anan Nattapong Somsak Prasert Wichai Kittisak Thanawat Sokha Dara Kyaw Aung Zaw Phonsavanh Souksavanh Chanthavong",
            "Srisuk Chaiyaporn Saetang Wongsakul Thongchai Boonmee Sok Chea Kim Htun Win Myint Vongsa Phommachanh Sengdara Keomany"),
    "vn": ("Thanh Minh Tuan Hung Dung Quang Hai Long Nam Duc Phong Khanh Hoang Vinh",
           "Nguyen Tran Le Pham Hoang Vo Phan Truong Bui Dang Do Ngo Duong Ly"),
    "pacifico": ("Sione Viliami Semisi Tevita Ratu Josefa Joeli Waisale Peni Iosefa Pita Tavita Faleolo Michael John Peter Henry Daniel Jacob Samuel",
                 "Tupou Fifita Vaipulu Naufahu Ratumaitavuki Waqa Tuilagi Leota Faleafa Tuimavave Schuster Ah Mu Tauiliili Kauhalalalo Pomare "
                 "Kepa Moala Lolohea Taufa Kalolo Mataio Kemoeatu Wabuge Kila"),
}

CULTURA_POR_ISO = {}
for _cult, _isos in {
    "es": "AR BO CL CO EC PY PE UY VE CR CU SV GT HN MX NI PA PR DO ES AD GQ",
    "pt": "BR PT AO CV GW MZ ST TL",
    "en": "GB IE GI US CA AU NZ",
    "caribe": "AG AI BS BB BZ BM DM GD GY JM KY TC VG VI MS KN VC LC TT",
    "fr": "FR BE LU HT NC PF",
    "af_fr": "BJ BF CM TD KM CG CI GA GN MG ML NE CF CD SN TG SC MU",
    "af_oeste": "GH NG LR SL GM",
    "af_este": "KE UG TZ RW BI SS",
    "cuerno": "ET ER SO DJ",
    "af_sur": "ZA ZM ZW MW BW NA LS SZ",
    "arabe": "EG SD SA BH QA AE IQ JO KW LB OM PS SY YE",
    "magreb": "DZ MA TN LY MR",
    "de": "DE AT LI CH",
    "nl": "NL AW CW SR",
    "it": "IT SM",
    "malta": "MT",
    "nordico": "DK NO SE IS FO",
    "fi": "FI",
    "baltico": "EE LV LT",
    "eslavo": "RU UA BY PL CZ SK SI HR RS BA ME MK BG",
    "albanes": "AL XK",
    "griego": "GR CY",
    "rumano": "RO MD",
    "hungaro": "HU",
    "turco": "TR AZ",
    "caucaso": "GE AM",
    "israel": "IL",
    "centroasia": "KZ KG TM UZ TJ",
    "persa": "IR AF",
    "sudasia": "IN NP BT LK",
    "sudasia_m": "PK BD MV",
    "chino": "CN HK TW MO SG",
    "kr": "KR KP",
    "jp": "JP",
    "mn": "MN",
    "indomalayo": "ID MY BN",
    "filipino": "PH",
    "tai": "TH LA KH MM",
    "vn": "VN",
    "pacifico": "FJ TO WS SB VU PG CK AS GU",
}.items():
    for _iso in _isos.split():
        CULTURA_POR_ISO[_iso] = _cult

# Apodos: van entre comillas en medio del nombre. Solo en las culturas donde se usan así en los medios deportivos.
APODOS = {
    "es": ["El Profe", "El Tanque", "El Pájaro", "El Flaco", "El Doctor", "El Tigre", "El Mago", "El Toro", "El Loco", "El Brujo", "El Maestro",
           "El Lobo", "El Gallo", "El Halcón", "El Trueno", "La Voz", "El Comandante", "El Ingeniero", "El Sabio", "El Relámpago", "El Capi", "El Pibe"],
    "pt": ["O Professor", "Tigrão", "O Mago", "Paredão", "Bigode", "Canhota", "O Doutor", "Furacão", "A Voz", "Trovão", "Lobo", "O Maestro", "Baixinho"],
    "en": ["The Voice", "The Professor", "Spider", "The Gaffer", "Tank", "Doc", "Maestro", "Sparky", "The Hawk", "Smudge", "Chalky", "Thunder"],
    "caribe": ["The Voice", "Doc", "Tank", "Maestro", "Thunder", "Spider", "Big Man"],
    "it": ["Il Professore", "Il Mago", "La Voce", "Il Leone", "Il Dottore", "Il Falco", "Il Bomber", "Il Maestro", "Il Lupo"],
    "fr": ["Le Professeur", "Le Sorcier", "La Voix", "Le Lion", "Le Docteur", "Le Faucon", "Le Maestro", "Le Loup"],
    "af_fr": ["Le Professeur", "La Voix", "Le Lion", "Le Docteur", "Le Maestro", "Le Sorcier"],
    "af_oeste": ["The Voice", "Doc", "Professor", "Maestro", "Lion"],
}
PROB_APODO = {"comentarista": 0.4, "periodista": 0.2}
APELLIDO_PRIMERO = {"chino", "kr", "vn"}   # ahí el apellido va primero («Zhao Lei», «Kim Min-jun»)


PREFIJOS = {"de", "van", "der", "den", "Ben", "El", "Ould", "De", "Ah", "Dela", "Al"}


def lista(texto: str):
    """Palabras de la lista, uniendo los apellidos compuestos («de Jong», «van den Berg», «Ben Salah», «Dela Cruz»)."""
    salida, buffer = [], []
    for t in texto.split():
        buffer.append(t)
        if t not in PREFIJOS:
            salida.append(" ".join(buffer))
            buffer = []
    return salida
