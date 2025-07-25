# -*- coding: utf-8 -*-
"""GAN & CNN.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1RnLsKK0X5Gzv41tVMBDAjsby7mSexINQ

cnn
"""

import os
import cv2
import torch
from torch.utils.data import Dataset
import numpy as np

class TamilNaduClimateDataset(Dataset):
    def __init__(self, image_dir, mask_dir, transform=None):
        self.image_dir = image_dir
        self.mask_dir = mask_dir
        self.image_files = sorted([
            f for f in os.listdir(image_dir) if f.endswith(".png")
        ])
        self.transform = transform

    def __len__(self):
        return len(self.image_files)

    def __getitem__(self, idx):
        img_path = os.path.join(self.image_dir, self.image_files[idx])
        mask_path = os.path.join(
            self.mask_dir, self.image_files[idx].replace(".png", "_mask.png")
        )

        image = cv2.imread(img_path)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)

        image = cv2.resize(image, (256, 256)) / 255.0
        mask = cv2.resize(mask, (256, 256), interpolation=cv2.INTER_NEAREST)

        image = torch.tensor(image.transpose(2, 0, 1), dtype=torch.float32)
        mask = torch.tensor(mask, dtype=torch.long)

        return image, mask

"""model_unet."""

import torch
import torch.nn as nn

class DoubleConv(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(DoubleConv, self).__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, 3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True)
        )

    def forward(self, x):
        return self.conv(x)

class UNet(nn.Module):
    def __init__(self, in_channels=3, out_classes=10):
        super(UNet, self).__init__()
        self.down1 = DoubleConv(in_channels, 64)
        self.down2 = DoubleConv(64, 128)
        self.down3 = DoubleConv(128, 256)
        self.down4 = DoubleConv(256, 512)

        self.pool = nn.MaxPool2d(2)
        self.middle = DoubleConv(512, 1024)

        self.up4 = nn.ConvTranspose2d(1024, 512, 2, 2)
        self.up_conv4 = DoubleConv(1024, 512)
        self.up3 = nn.ConvTranspose2d(512, 256, 2, 2)
        self.up_conv3 = DoubleConv(512, 256)
        self.up2 = nn.ConvTranspose2d(256, 128, 2, 2)
        self.up_conv2 = DoubleConv(256, 128)
        self.up1 = nn.ConvTranspose2d(128, 64, 2, 2)
        self.up_conv1 = DoubleConv(128, 64)

        self.final = nn.Conv2d(64, out_classes, kernel_size=1)

    def forward(self, x):
        d1 = self.down1(x)
        d2 = self.down2(self.pool(d1))
        d3 = self.down3(self.pool(d2))
        d4 = self.down4(self.pool(d3))
        m = self.middle(self.pool(d4))

        u4 = self.up4(m)
        u4 = self.up_conv4(torch.cat([u4, d4], dim=1))
        u3 = self.up3(u4)
        u3 = self.up_conv3(torch.cat([u3, d3], dim=1))
        u2 = self.up2(u3)
        u2 = self.up_conv2(torch.cat([u2, d2], dim=1))
        u1 = self.up1(u2)
        u1 = self.up_conv1(torch.cat([u1, d1], dim=1))

        return self.final(u1)

"""


predict_and_visualize
"""

import torch
import matplotlib.pyplot as plt
import numpy as np
from cnn.dataset import TamilNaduClimateDataset
from cnn.model_unet import UNet
import os

label_colors = {
    0: (255, 255, 255),  # Unclassified - White
    1: (0, 0, 255),      # Cold - Blue
    2: (100, 150, 255),  # Cool - Light Blue
    3: (0, 255, 0),      # Mild - Green
    4: (180, 220, 60),   # Warm - Yellow-Green
    5: (255, 255, 0),    # Hot - Yellow
    6: (0, 0, 128),      # Water - Navy Blue
    7: (160, 160, 160),  # Urban - Gray
    8: (0, 100, 0),      # Forest - Dark Green
    9: (210, 180, 140),  # Dry/Affected - Tan
}

def decode_segmap(mask):
    h, w = mask.shape
    rgb_mask = np.zeros((h, w, 3), dtype=np.uint8)
    for class_id, color in label_colors.items():
        rgb_mask[mask == class_id] = color
    return rgb_mask

def visualize_prediction(index=0):
    image_dir = "/content/drive/MyDrive/TamilNaduClimate/images"
    mask_dir = "/content/drive/MyDrive/TamilNaduClimate/masks"
    model_path = "checkpoints/unet_classifier.pth"

    dataset = TamilNaduClimateDataset(image_dir, mask_dir)
    image, true_mask = dataset[index]
    input_tensor = image.unsqueeze(0).to("cuda" if torch.cuda.is_available() else "cpu")

    model = UNet(in_channels=3, out_classes=10)
    model.load_state_dict(torch.load(model_path, map_location="cpu"))
    model.eval()

    with torch.no_grad():
        output = model(input_tensor)
        pred_mask = torch.argmax(output.squeeze(), dim=0).cpu().numpy()

    # Convert tensors to displayable formats
    image_np = image.permute(1, 2, 0).numpy()
    true_mask_np = decode_segmap(true_mask.numpy())
    pred_mask_np = decode_segmap(pred_mask)

    # Plot side-by-side
    plt.figure(figsize=(15, 5))
    plt.subplot(1, 3, 1)
    plt.imshow(image_np)
    plt.title("Input Image")
    plt.axis("off")

    plt.subplot(1, 3, 2)
    plt.imshow(true_mask_np)
    plt.title("Ground Truth Mask")
    plt.axis("off")

    plt.subplot(1, 3, 3)
    plt.imshow(pred_mask_np)
    plt.title("Predicted Mask")
    plt.axis("off")

    plt.tight_layout()
    plt.show()

# Example usage:
# visualize_prediction(index=5)

from cnn.model_unet import UNet
from dataset import TamilNaduClimateDataset
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

image_dir = "/content/drive/MyDrive/TamilNaduClimate/images"
mask_dir = "/content/drive/MyDrive/TamilNaduClimate/masks"

dataset = TamilNaduClimateDataset(image_dir, mask_dir)
loader = DataLoader(dataset, batch_size=4, shuffle=True)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = UNet(in_channels=3, out_classes=10).to(device)
criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=1e-4)

for epoch in range(10):  # Modify as needed
    model.train()
    for img, mask in loader:
        img, mask = img.to(device), mask.to(device)
        output = model(img)
        loss = criterion(output, mask)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    print(f"Epoch {epoch+1}, Loss: {loss.item():.4f}")

torch.save(model.state_dict(), "/content/unet_final.pth")

"""GAN"""

import torch
import torch.nn as nn

class Discriminator(nn.Module):
    def __init__(self, img_channels=3):
        super(Discriminator, self).__init__()
        self.model = nn.Sequential(
            nn.Conv2d(img_channels, 64, 4, 2, 1),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(64, 128, 4, 2, 1),
            nn.BatchNorm2d(128),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(128, 256, 4, 2, 1),
            nn.BatchNorm2d(256),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(256, 1, 4, 2, 0),
            nn.Flatten(),
            nn.Sigmoid()
        )

    def forward(self, img):
        return self.model(img)

import torch
import torchvision
import os

def save_generated_images(generator, z_dim, device, epoch, output_dir="gan_outputs"):
    generator.eval()
    with torch.no_grad():
        z = torch.randn(16, z_dim).to(device)
        fake_images = generator(z)
        fake_images = (fake_images + 1) / 2  # Convert to [0, 1]
        os.makedirs(output_dir, exist_ok=True)
        torchvision.utils.save_image(fake_images, f"{output_dir}/epoch_{epoch}.png", nrow=4)
    generator.train()

import torch
import os
from torchvision.utils import save_image
from gan.generator import Generator

def generate_future_images(
    generator_path,
    output_dir,
    z_dim=256,
    num_images=9125,  # 25 years × 365 days
    device="cuda" if torch.cuda.is_available() else "cpu"
):
    os.makedirs(output_dir, exist_ok=True)

    # Load trained generator
    generator = Generator(z_dim=z_dim).to(device)
    generator.load_state_dict(torch.load(generator_path, map_location=device))
    generator.eval()

    # Generate images
    with torch.no_grad():
        for i in range(num_images):
            z = torch.randn(1, z_dim).to(device)
            fake_img = generator(z)
            fake_img = (fake_img + 1) / 2  # scale from [-1,1] to [0,1]
            save_path = os.path.join(output_dir, f"gen_day_{i+1:04d}.png")
            save_image(fake_img, save_path)
            if (i + 1) % 500 == 0:
                print(f"✅ Generated {i + 1} / {num_images} images")

    print(f"\n🎉 Done! All {num_images} future images saved in: {output_dir}")

# Example usage
if __name__ == "__main__":
    generate_future_images(
        generator_path="/content/drive/MyDrive/TIZZY/checkpoints/gan_generator.pth",
        output_dir="/content/drive/MyDrive/TIZZY/generated/"
    )

import torch
import torch.nn as nn

class Generator(nn.Module):
    def __init__(self, z_dim=256, img_channels=3):
        super(Generator, self).__init__()
        self.model = nn.Sequential(
            nn.Linear(z_dim, 1024 * 4 * 4),
            nn.ReLU(True),
            nn.Unflatten(1, (1024, 4, 4)),
            nn.ConvTranspose2d(1024, 512, 4, 2, 1),
            nn.BatchNorm2d(512),
            nn.ReLU(True),
            nn.ConvTranspose2d(512, 256, 4, 2, 1),
            nn.BatchNorm2d(256),
            nn.ReLU(True),
            nn.ConvTranspose2d(256, 128, 4, 2, 1),
            nn.BatchNorm2d(128),
            nn.ReLU(True),
            nn.ConvTranspose2d(128, img_channels, 4, 2, 1),
            nn.Tanh()
        )

    def forward(self, z):
        return self.model(z)

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from torchvision.utils import save_image
from torchvision import transforms
from PIL import Image
import os
import numpy as np

from gan.generator import Generator
from gan.discriminator import Discriminator
from gan.gan_utils import save_generated_images

# --- Dataset class ---
class SatelliteDataset(Dataset):
    def __init__(self, image_dir):
        self.image_dir = image_dir
        self.image_files = [f for f in os.listdir(image_dir) if f.endswith('.png')]

    def __len__(self):
        return len(self.image_files)

    def __getitem__(self, idx):
        img_path = os.path.join(self.image_dir, self.image_files[idx])
        image = Image.open(img_path).convert("RGB").resize((64, 64))
        image = np.array(image).astype(np.float32) / 127.5 - 1.0  # Normalize to [-1, 1]
        image = torch.tensor(image).permute(2, 0, 1)
        return image

# --- Generate synthetic future images (2026–2050) ---
def generate_future_images(generator, z_dim=256, output_dir="/content/drive/MyDrive/tamilnadu_gan_images/", num_images=9125, device="cuda" if torch.cuda.is_available() else "cpu"):
    os.makedirs(output_dir, exist_ok=True)
    generator.eval()
    with torch.no_grad():
        for i in range(num_images):
            z = torch.randn(1, z_dim).to(device)
            fake_img = generator(z)
            fake_img = (fake_img + 1) / 2  # Convert from [-1,1] to [0,1]
            save_path = os.path.join(output_dir, f"gen_day_{i+1:04d}.png")
            save_image(fake_img, save_path)
            if (i + 1) % 500 == 0:
                print(f"✅ Generated {i + 1} / {num_images} images")
    print(f"\n🎉 Done! All {num_images} future images saved to: {output_dir}")

# --- Train GAN ---
def train_gan():
    z_dim = 256
    img_channels = 3
    batch_size = 32
    num_epochs = 2000
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    dataset = SatelliteDataset("/content/drive/MyDrive/tamilnadu_png_images")
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    generator = Generator(z_dim, img_channels).to(device)
    discriminator = Discriminator(img_channels).to(device)

    criterion = nn.BCELoss()
    g_optimizer = optim.Adam(generator.parameters(), lr=2e-4, betas=(0.5, 0.999))
    d_optimizer = optim.Adam(discriminator.parameters(), lr=2e-4, betas=(0.5, 0.999))

    for epoch in range(num_epochs):
        for batch in loader:
            batch = batch.to(device)
            real_labels = torch.ones(batch.size(0), 1).to(device)
            fake_labels = torch.zeros(batch.size(0), 1).to(device)

            # Train Discriminator
            outputs = discriminator(batch)
            d_loss_real = criterion(outputs, real_labels)

            z = torch.randn(batch.size(0), z_dim).to(device)
            fake_images = generator(z)
            outputs = discriminator(fake_images.detach())
            d_loss_fake = criterion(outputs, fake_labels)

            d_loss = d_loss_real + d_loss_fake
            d_optimizer.zero_grad()
            d_loss.backward()
            d_optimizer.step()

            # Train Generator
            z = torch.randn(batch.size(0), z_dim).to(device)
            fake_images = generator(z)
            outputs = discriminator(fake_images)
            g_loss = criterion(outputs, real_labels)

            g_optimizer.zero_grad()
            g_loss.backward()
            g_optimizer.step()

        print(f"Epoch [{epoch+1}/{num_epochs}] | D Loss: {d_loss.item():.4f} | G Loss: {g_loss.item():.4f}")

        if (epoch + 1) % 10 == 0:
            save_generated_images(generator, z_dim, device, epoch + 1)

    # --- Save model checkpoints ---
    os.makedirs("gan_outputs", exist_ok=True)
    torch.save(generator.state_dict(), "gan_outputs/generator.pth")
    torch.save(discriminator.state_dict(), "gan_outputs/discriminator.pth")

    # --- Automatically generate future climate images ---
    generate_future_images(
        generator=generator,
        z_dim=z_dim,
        output_dir="/content/drive/MyDrive/tamilnadu_gan_images",
        num_images=9125,
        device=device
    )

if __name__ == "__main__":
    train_gan()