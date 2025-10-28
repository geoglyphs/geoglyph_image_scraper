import os
import shutil
import tkinter as tk
from PIL import Image, ImageTk

# Folder Paths
INPUT_FOLDER = "circle/" # set input folder containing images to review
KEEP_FOLDER = "keep/"
DISCARD_FOLDER = "discard/"

# Create output folders if they don't exist
os.makedirs(KEEP_FOLDER, exist_ok=True)
os.makedirs(DISCARD_FOLDER, exist_ok=True)

# Load Images 
images  = [f for f in os.listdir(INPUT_FOLDER) if f.endswith('.png')]
num_images = len(images)
index = 0

#shows images one by one
def show_img():
    global img_label, index 
    if index >= num_images:
        print("No more images to review.")
        root.quit()
        return
    img_path = os.path.join(INPUT_FOLDER, images[index])
    img = Image.open(img_path)
    img = img.resize((500, 500))
    img_tk = ImageTk.PhotoImage(img)
    img_label.config(image=img_tk)
    img_label.image = img_tk
    root.title(f"Image {index + 1} of {num_images}")

# copies image to keep or discard folder
def move_img(folder):
    global index
    src = os.path.join(INPUT_FOLDER, images[index])
    shutil.copy(src, os.path.join(folder, images[index]))
    index += 1
    show_img()

# applies move_img function to keep/discard folders
def keep_img(_event = None):
    move_img(KEEP_FOLDER)

def discard_img(_event = None):
    move_img(DISCARD_FOLDER)

root = tk.Tk()
root.geometry("600x600")

img_label = tk.Label(root, bg="black")
img_label.pack(expand=True)

#keep and discard buttons 
btn_frame = tk.Frame(root, bg="#222")
btn_frame.pack(pady=15)

tk.Button(btn_frame, text="KEEP: Right Arrow →", command=keep_img,
          width=20, height=2, bg="#2ecc71").grid(row=0, column=1, padx=10)
tk.Button(btn_frame, text="← DISCARD: Left Arrow", command=discard_img,
          width=20, height=2, bg="#e74c3c").grid(row=0, column=0, padx=10)


root.bind("<Right>", keep_img)     # right arrow = Keep
root.bind("<Left>", discard_img)   # left arrow = Discard

show_img()

root.mainloop()