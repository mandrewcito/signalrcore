using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Identity.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore;

namespace SignalRAuthenticationSample.Data
{
    public class ApplicationDbContext : IdentityDbContext<ApplicationUser>
    {
        public ApplicationDbContext(DbContextOptions<ApplicationDbContext> options)
            : base(options)
        {
        }

        protected override void OnModelCreating(ModelBuilder builder)
        {
            base.OnModelCreating(builder);
            // Customize the ASP.NET Core Identity model and override the defaults if needed.
            // For example, you can rename the ASP.NET Core Identity table names and more.
            // Add your customizations after calling base.OnModelCreating(builder);

                
     ApplicationUser appUser = new ApplicationUser
        {
            UserName = "mandrewcito",
            Email = "MM@GMAIL.COM",
            NormalizedEmail = "MM@GMAIL.COM".ToUpper(),
            NormalizedUserName = "mandrewcito".ToUpper(),
            TwoFactorEnabled = false,
            EmailConfirmed = true,
            PhoneNumber = "123456789",
            PhoneNumberConfirmed = false
        };

        PasswordHasher<ApplicationUser> ph = new PasswordHasher<ApplicationUser>();
        appUser.PasswordHash = ph.HashPassword(appUser, "DDbc123._");
/*
        builder.Entity<IdentityRole>().HasData(
            new IdentityRole { Name = "Admin", NormalizedName = "ADMIN" },
            new IdentityRole { Name = "User", NormalizedName = "USER"}
        );
 */
        builder.Entity<ApplicationUser>().HasData(
            appUser
        );

        }
    }
}
