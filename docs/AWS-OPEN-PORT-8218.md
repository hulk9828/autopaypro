# Open port 8218 on AWS so the app is reachable from the internet

Your app works on the server (`curl http://127.0.0.1:8218` OK) but **times out** from outside because AWS Security Group is blocking port 8218. Do this in the AWS Console:

## Steps (do every step)

1. **Log in** to [AWS Console](https://console.aws.amazon.com/) → go to **EC2**.

2. **Instances** (left menu) → select your instance (the one with public IP `18.188.184.213`).  
   - Confirm the **Public IPv4 address** is `18.188.184.213`.

3. Open the **Security** tab (below the instance list).  
   - You’ll see **Security groups** with a link like `sg-0abc123...` (launch-wizard-1 or default).  
   - **Click that Security group name** (the blue link).

4. In the Security group page:
   - Go to the **Inbound rules** tab.
   - Click **Edit inbound rules**.

5. **Add rule:**
   - Click **Add rule**.
   - **Type:** choose **Custom TCP** (from the dropdown).
   - **Port range:** type `8218` (only this number).
   - **Source:** choose **Anywhere-IPv4** (so **0.0.0.0/0** appears).  
     (Or choose “My IP” if you only want your current IP.)
   - Leave other fields as default.

6. Click **Save rules**.

7. **Test** (from your laptop or phone, not the server):
   - Open in browser: `http://18.188.184.213:8218/docs`
   - Or run: `curl http://18.188.184.213:8218/api/v1/health`

If it still times out, confirm you edited the **same** Security group that is attached to your instance (step 3), and that the rule shows **Custom TCP**, port **8218**, source **0.0.0.0/0**.
