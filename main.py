import nextcord, json, requests, re, certifi
from nextcord.ext import commands
import cloudscraper
import logging


bot, config = commands.Bot(command_prefix='flexzy!',help_command=None,intents=nextcord.Intents.all()), json.load(open('./config.json', 'r', encoding='utf-8'))


class TopupModal(nextcord.ui.Modal):
    def __init__(self):
        super().__init__(title='กรอกลิ้งค์อั่งเปาของท่าน')
        self.a = nextcord.ui.TextInput(
            label='ลิ้งค์ซองอังเปา',
            placeholder='https://gift.truemoney.com/campaign/?v=xxxxxxxxxxxxxxx',
            style=nextcord.TextInputStyle.short,
            required=True
        )
        self.add_item(self.a)

    async def callback(self, interaction: nextcord.Interaction):
        link = str(self.a.value).strip()
        if re.match(r'https:\/\/gift\.truemoney\.com\/campaign\/\?v=[a-zA-Z0-9]{18}', link):
            logging.info(f'URL {link} DISCORD-ID {interaction.user.id}')

            if 'phone' not in config:
                embed = nextcord.Embed(description='เกิดข้อผิดพลาดในการตั้งค่า: หมายเลขโทรศัพท์ไม่ถูกต้อง', color=nextcord.Color.red())
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            voucher_code = link.split("?v=")[1]
            verification_url = f"https://gift.truemoney.com/campaign/vouchers/{voucher_code}/verify?mobile={config['phone']}"
            redeem_url = f"https://gift.truemoney.com/campaign/vouchers/{voucher_code}/redeem"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'en-US,en;q=0.9',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'TE': 'Trailers'
            }

            try:
                scraper = cloudscraper.create_scraper()

                verify_response = scraper.get(verification_url, headers=headers)
                logging.info(f'Verify Response Content: {verify_response.text}')

                if verify_response.status_code == 200:
                    data = verify_response.json()
                    voucher_status = data.get("data", {}).get("voucher", {}).get("status")

                    if voucher_status == "active":
                        redeem_response = scraper.post(redeem_url, json={"mobile": config['phone']}, headers=headers)
                        logging.info(f'Redeem Response Content: {redeem_response.text}')
                        redeem_data = redeem_response.json()

                        if redeem_response.status_code == 200 and redeem_data.get("status", {}).get("code") == "SUCCESS":
                            amount = float(redeem_data["data"]["my_ticket"]["amount_baht"])

                            try:
                                with open("./database/users.json", "r", encoding="utf-8") as file:
                                    userJSON = json.load(file)
                            except (FileNotFoundError, json.JSONDecodeError) as e:
                                embed = nextcord.Embed(description='เกิดข้อผิดพลาดในการอ่านข้อมูลผู้ใช้', color=nextcord.Color.red())
                                await interaction.response.send_message(embed=embed, ephemeral=True)
                                return

                            user_data = userJSON.get(str(interaction.user.id), {"point": 0, "all-point": 0, "transaction": []})
                            user_data["point"] += amount
                            user_data["all-point"] += amount
                            user_data["transaction"].append({
                                "topup": {
                                    "url": link,
                                    "amount": amount,
                                    "time": str(datetime.now()),
                                }
                            })
                            userJSON[str(interaction.user.id)] = user_data

                            try:
                                with open("./database/users.json", "w", encoding="utf-8") as file:
                                    json.dump(userJSON, file, indent=4, ensure_ascii=False)
                            except IOError as e:
                                embed = nextcord.Embed(description='เกิดข้อผิดพลาดในการบันทึกข้อมูลผู้ใช้', color=nextcord.Color.red())
                                await interaction.response.send_message(embed=embed, ephemeral=True)
                                return

                            embed = nextcord.Embed(
                                description=f'✅﹒**เติมเงินสำเร็จ**\nจำนวนเงิน: {amount} บาท',
                                color=nextcord.Color.green()
                            )
                        elif redeem_response.status_code == 405:
                            embed = nextcord.Embed(description='⚠﹒เกิดข้อผิดพลาดในการแลกซองอั่งเปา: Method Not Allowed', color=nextcord.Color.red())
                        else:
                            reason = redeem_data.get("status", {}).get("message", "Unknown error")
                            embed = nextcord.Embed(description=f'❌﹒เกิดข้อผิดพลาดในการแลกซองอั่งเปา: {reason}', color=nextcord.Color.red())
                    elif voucher_status == "redeemed":
                        embed = nextcord.Embed(description='❌﹒ซองอั่งเปานี้ถูกใช้ไปแล้ว', color=nextcord.Color.red())
                    elif voucher_status == "expired":
                        embed = nextcord.Embed(description='❌﹒ซองอั่งเปานี้หมดอายุแล้ว', color=nextcord.Color.red())
                    else:
                        reason = data.get("status", {}).get("message", "Unknown error")
                        embed = nextcord.Embed(description=f'❌﹒เกิดข้อผิดพลาด: {reason}', color=nextcord.Color.red())

                elif verify_response.status_code == 403:
                    embed = nextcord.Embed(description='❌﹒ซองอั่งเปานี้หมดอายุแล้วหรือถูกใช้ไปแล้ว', color=nextcord.Color.red())
                else:
                    embed = nextcord.Embed(description='⚠﹒เกิดข้อผิดพลาดในการตรวจสอบซองอั่งเปา', color=nextcord.Color.red())

            except Exception as e:
                embed = nextcord.Embed(description=f'เกิดข้อผิดพลาดในการเชื่อมต่อ: {e}', color=nextcord.Color.red())
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        else:
            embed = nextcord.Embed(description='⚠﹒ลิ้งค์ที่ให้มาไม่ถูกต้อง', color=nextcord.Color.red())

        await interaction.response.send_message(embed=embed, ephemeral=True)

class BuyView(nextcord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)
        self.link_button = nextcord.ui.Button(style=nextcord.ButtonStyle.link, label="จ้างทำบอท", url='https://discord.gg/flexzy') 
        self.add_item(self.link_button)

    @nextcord.ui.button(label='[🧧] เติมเงิน', custom_id='buyRole', style=nextcord.ButtonStyle.blurple)
    async def buyRole(self, button: nextcord.Button, interaction: nextcord.Interaction):
        await interaction.response.send_modal(BuyModal())

    @nextcord.ui.button(label='[🛒] ราคายศทั้งหมด', custom_id='priceRole', style=nextcord.ButtonStyle.blurple)
    async def priceRole(self, button: nextcord.Button, interaction: nextcord.Interaction):
        description = ''
        for roleData in config['roleSettings']:
            description += f'เติมเงิน {roleData["price"]} บาท จะได้รับยศ\n𓆩⟡𓆪  <@&{roleData["roleId"]}>\n₊✧──────✧₊∘\n'
        embed = nextcord.Embed(
            title='ราคายศทั้งหมด',
            color=nextcord.Color.from_rgb(93, 176, 242),
            description=description
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_ready():
    bot.add_view(BuyView())
    print(f"""          LOGIN AS: {bot.user}
    Successfully reloaded application [/] commands.""")

@bot.slash_command(name='setup',description='setup')
async def setup(interaction: nextcord.Interaction):
    if (int(interaction.user.id) == int(config['ownerId'])):
        await interaction.channel.send(embed=nextcord.Embed(
            title='**【⭐】Flexzy Store Topup**',
            description='ซื้อยศอัตโนมัติ 24ชั่วโมง\n・กดปุ่ม "เติมเงิน" เพื่อซื้อยศ\n・กดปุ่ม "ราคายศ" เพื่อดูราคายศ',
            color=nextcord.Color.from_rgb(100, 220, 255),
        ).set_thumbnail(url='https://cdn.discordapp.com/attachments/1105860649294237846/1171859094999662693/flexzyz.png?ex=65a809d4&is=659594d4&hm=463b298fab99c869af55ddc8c6379830c00a145e161c1bcd181ac4ba975e3912&')
        .set_image(url='https://images-ext-1.discordapp.net/external/JDnpFIEpRqs3lXwgtc6zk023mQP0KD5GDkXbRbWkAUM/https/www.checkraka.com/uploaded/img/content/130026/aungpao_truewallet_01.jpg?format=webp&width=810&height=540'), view=BuyView())
        await interaction.response.send_message((
        'Successfully reloaded application [/] commands.'
        ), ephemeral=True)
    else:
        await interaction.response.send_message((
           'มึงไม่ได้เป็น Owner ไอควาย ใช้ไม่ได้'
        ), ephemeral=True)

bot.run(config['token'])